#define NOMINMAX
#include <windows.h>

#include <opencv2/opencv.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "../windows_virtual_camera/shared/CamCompositeSharedFrame.h"

#ifdef min
#undef min
#endif

#ifdef max
#undef max
#endif

static constexpr int OUTPUT_W = 1920;
static constexpr int OUTPUT_H = 1080;
static constexpr int FPS = 30;

static const std::string CONTROL_FILE_PATH = "runtime/control.txt";

struct EngineControl
{
    std::string mode;
    std::vector<int> cameraIndexes;
};

class SharedFrameWriter
{
private:
    HANDLE hMap = NULL;
    CamCompositeSharedFrame* shared = nullptr;

    static BYTE clampByte(int value)
    {
        if (value < 0) return 0;
        if (value > 255) return 255;
        return static_cast<BYTE>(value);
    }

    static void bgrToYuv(BYTE b, BYTE g, BYTE r, BYTE& y, BYTE& u, BYTE& v)
    {
        int yy = ((66 * r + 129 * g + 25 * b + 128) >> 8) + 16;
        int uu = ((-38 * r - 74 * g + 112 * b + 128) >> 8) + 128;
        int vv = ((112 * r - 94 * g - 18 * b + 128) >> 8) + 128;

        y = clampByte(yy);
        u = clampByte(uu);
        v = clampByte(vv);
    }

public:
    bool open()
    {
        hMap = CreateFileMappingW(
            INVALID_HANDLE_VALUE,
            NULL,
            PAGE_READWRITE,
            0,
            sizeof(CamCompositeSharedFrame),
            CAMCOMP_SHARED_MEMORY_NAME
        );

        if (!hMap)
        {
            std::cerr << "CreateFileMapping failed: " << GetLastError() << "\n";
            return false;
        }

        shared = static_cast<CamCompositeSharedFrame*>(
            MapViewOfFile(
                hMap,
                FILE_MAP_ALL_ACCESS,
                0,
                0,
                sizeof(CamCompositeSharedFrame)
            )
        );

        if (!shared)
        {
            std::cerr << "MapViewOfFile failed: " << GetLastError() << "\n";
            CloseHandle(hMap);
            hMap = NULL;
            return false;
        }

        ZeroMemory(shared, sizeof(CamCompositeSharedFrame));

        shared->magic = CAMCOMP_MAGIC;
        shared->version = CAMCOMP_VERSION;
        shared->width = CAMCOMP_WIDTH;
        shared->height = CAMCOMP_HEIGHT;
        shared->bytesPerPixel = CAMCOMP_BYTES_PER_PIXEL;
        shared->frameSize = CAMCOMP_FRAME_SIZE;
        shared->bufferCount = CAMCOMP_BUFFER_COUNT;
        shared->writing = 0;
        shared->readableBufferIndex = 0;
        shared->frameIndex = 0;

        std::cout << "Shared frame buffer ready with double buffering\n";
        return true;
    }

    void writeBgrFrame(const cv::Mat& bgrFrame)
    {
        if (!shared || bgrFrame.empty())
            return;

        cv::Mat frame;

        if (bgrFrame.cols != CAMCOMP_WIDTH || bgrFrame.rows != CAMCOMP_HEIGHT)
        {
            cv::resize(
                bgrFrame,
                frame,
                cv::Size(CAMCOMP_WIDTH, CAMCOMP_HEIGHT),
                0,
                0,
                cv::INTER_AREA
            );
        }
        else
        {
            frame = bgrFrame;
        }

        if (!frame.isContinuous())
        {
            frame = frame.clone();
        }

        LONG currentReadable = shared->readableBufferIndex;

        if (currentReadable < 0 || currentReadable >= CAMCOMP_BUFFER_COUNT)
        {
            currentReadable = 0;
        }

        LONG writeBufferIndex = 1 - currentReadable;

        shared->writing = 1;
        MemoryBarrier();

        BYTE* dst = shared->buffers[writeBufferIndex];

        for (int y = 0; y < CAMCOMP_HEIGHT; y++)
        {
            const BYTE* row = frame.ptr<BYTE>(y);

            for (int x = 0; x < CAMCOMP_WIDTH; x += 2)
            {
                const BYTE* p0 = row + x * 3;
                const BYTE* p1 = row + (x + 1) * 3;

                BYTE y0, u0, v0;
                BYTE y1, u1, v1;

                bgrToYuv(p0[0], p0[1], p0[2], y0, u0, v0);
                bgrToYuv(p1[0], p1[1], p1[2], y1, u1, v1);

                BYTE u = static_cast<BYTE>((static_cast<int>(u0) + static_cast<int>(u1)) / 2);
                BYTE v = static_cast<BYTE>((static_cast<int>(v0) + static_cast<int>(v1)) / 2);

                int offset = (y * CAMCOMP_WIDTH + x) * 2;

                dst[offset + 0] = y0;
                dst[offset + 1] = u;
                dst[offset + 2] = y1;
                dst[offset + 3] = v;
            }
        }

        MemoryBarrier();

        shared->readableBufferIndex = writeBufferIndex;
        shared->frameIndex++;
        shared->writing = 0;
    }

    void close()
    {
        if (shared)
        {
            UnmapViewOfFile(shared);
            shared = nullptr;
        }

        if (hMap)
        {
            CloseHandle(hMap);
            hMap = NULL;
        }
    }

    ~SharedFrameWriter()
    {
        close();
    }
};

class CameraReader
{
public:
    CameraReader(int index) : cameraIndex(index) {}

    bool start()
    {
        if (!openCamera())
        {
            std::cerr << "Failed to open camera index " << cameraIndex << "\n";
            return false;
        }

        running = true;
        worker = std::thread(&CameraReader::loop, this);
        return true;
    }

    bool readLatest(cv::Mat& out)
    {
        std::lock_guard<std::mutex> lock(frameMutex);

        if (latestFrame.empty())
        {
            return false;
        }

        latestFrame.copyTo(out);
        return true;
    }

    void stop()
    {
        running = false;

        if (worker.joinable())
        {
            worker.join();
        }

        if (cap.isOpened())
        {
            cap.release();
        }
    }

    ~CameraReader()
    {
        stop();
    }

private:
    int cameraIndex;
    cv::VideoCapture cap;
    std::atomic<bool> running{false};
    std::thread worker;
    std::mutex frameMutex;
    cv::Mat latestFrame;
    int failedReads = 0;

    bool openCamera()
    {
        if (cap.isOpened())
        {
            cap.release();
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(150));

        std::cout << "Opening camera index " << cameraIndex << "...\n";

        cap.open(cameraIndex, cv::CAP_DSHOW);

        if (!cap.isOpened())
        {
            return false;
        }

        cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
        cap.set(cv::CAP_PROP_FRAME_WIDTH, OUTPUT_W);
        cap.set(cv::CAP_PROP_FRAME_HEIGHT, OUTPUT_H);
        cap.set(cv::CAP_PROP_FPS, FPS);

        std::cout << "Actual camera " << cameraIndex << ": "
                  << cap.get(cv::CAP_PROP_FRAME_WIDTH) << "x"
                  << cap.get(cv::CAP_PROP_FRAME_HEIGHT) << "@"
                  << cap.get(cv::CAP_PROP_FPS) << "\n";

        return true;
    }

    void loop()
    {
        while (running)
        {
            cv::Mat frame;
            bool ok = cap.read(frame);

            if (ok && !frame.empty())
            {
                failedReads = 0;

                std::lock_guard<std::mutex> lock(frameMutex);
                latestFrame = frame.clone();
            }
            else
            {
                failedReads++;

                if (failedReads >= 60)
                {
                    std::cerr << "Camera " << cameraIndex << " stalled. Reopening...\n";
                    openCamera();
                    failedReads = 0;
                }

                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
    }
};

cv::Mat blank(int w, int h)
{
    return cv::Mat::zeros(h, w, CV_8UC3);
}

cv::Mat fitAndPad(const cv::Mat& frame, int boxW, int boxH)
{
    if (frame.empty())
    {
        return blank(boxW, boxH);
    }

    double scale = std::min(
        static_cast<double>(boxW) / frame.cols,
        static_cast<double>(boxH) / frame.rows
    );

    int newW = std::max(1, static_cast<int>(frame.cols * scale));
    int newH = std::max(1, static_cast<int>(frame.rows * scale));

    cv::Mat resized;
    cv::resize(frame, resized, cv::Size(newW, newH), 0, 0, cv::INTER_AREA);

    cv::Mat canvas = blank(boxW, boxH);

    int x = (boxW - newW) / 2;
    int y = (boxH - newH) / 2;

    resized.copyTo(canvas(cv::Rect(x, y, newW, newH)));
    return canvas;
}

cv::Mat composeFrames(const std::vector<cv::Mat>& frames, const std::string& mode)
{
    if (frames.empty())
    {
        return blank(OUTPUT_W, OUTPUT_H);
    }

    if (mode == "single" || frames.size() == 1)
    {
        return fitAndPad(frames[0], OUTPUT_W, OUTPUT_H);
    }

    if (mode == "pip" && frames.size() >= 2)
    {
        cv::Mat output = fitAndPad(frames[0], OUTPUT_W, OUTPUT_H);

        int pipW = OUTPUT_W / 4;
        int pipH = OUTPUT_H / 4;

        cv::Mat pip = fitAndPad(frames[1], pipW, pipH);

        int margin = 40;
        int x = OUTPUT_W - pipW - margin;
        int y = OUTPUT_H - pipH - margin;

        cv::rectangle(
            output,
            cv::Rect(x - 4, y - 4, pipW + 8, pipH + 8),
            cv::Scalar(255, 255, 255),
            cv::FILLED
        );

        pip.copyTo(output(cv::Rect(x, y, pipW, pipH)));
        return output;
    }

    if ((mode == "sbs" || mode == "side-by-side") && frames.size() >= 2)
    {
        cv::Mat left = fitAndPad(frames[0], OUTPUT_W / 2, OUTPUT_H);
        cv::Mat right = fitAndPad(frames[1], OUTPUT_W / 2, OUTPUT_H);

        cv::Mat output;
        cv::hconcat(left, right, output);
        return output;
    }

    if (mode == "stacked" && frames.size() >= 2)
    {
        cv::Mat top = fitAndPad(frames[0], OUTPUT_W, OUTPUT_H / 2);
        cv::Mat bottom = fitAndPad(frames[1], OUTPUT_W, OUTPUT_H / 2);

        cv::Mat output;
        cv::vconcat(top, bottom, output);
        return output;
    }

    if (mode == "triple" && frames.size() >= 3)
    {
        int cellW = OUTPUT_W / 2;
        int cellH = OUTPUT_H / 2;

        cv::Mat tl = fitAndPad(frames[0], cellW, cellH);
        cv::Mat blankCell = blank(cellW, cellH);
        cv::Mat bl = fitAndPad(frames[1], cellW, cellH);
        cv::Mat br = fitAndPad(frames[2], cellW, cellH);

        cv::Mat topRow;
        cv::hconcat(tl, blankCell, topRow);

        cv::Mat bottomRow;
        cv::hconcat(bl, br, bottomRow);

        cv::Mat output;
        cv::vconcat(topRow, bottomRow, output);
        return output;
    }

    if (mode == "quad" && frames.size() >= 4)
    {
        int cellW = OUTPUT_W / 2;
        int cellH = OUTPUT_H / 2;

        cv::Mat tl = fitAndPad(frames[0], cellW, cellH);
        cv::Mat tr = fitAndPad(frames[1], cellW, cellH);
        cv::Mat bl = fitAndPad(frames[2], cellW, cellH);
        cv::Mat br = fitAndPad(frames[3], cellW, cellH);

        cv::Mat topRow;
        cv::hconcat(tl, tr, topRow);

        cv::Mat bottomRow;
        cv::hconcat(bl, br, bottomRow);

        cv::Mat output;
        cv::vconcat(topRow, bottomRow, output);
        return output;
    }

    return fitAndPad(frames[0], OUTPUT_W, OUTPUT_H);
}

bool isNonBlack(const cv::Mat& frame)
{
    if (frame.empty())
        return false;

    cv::Scalar meanValue = cv::mean(frame);
    double brightness = meanValue[0] + meanValue[1] + meanValue[2];

    return brightness > 15.0;
}

std::string trim(const std::string& value)
{
    size_t start = value.find_first_not_of(" \t\r\n");
    if (start == std::string::npos)
    {
        return "";
    }

    size_t end = value.find_last_not_of(" \t\r\n");
    return value.substr(start, end - start + 1);
}

std::vector<int> parseCameraList(const std::string& value)
{
    std::vector<int> result;
    std::stringstream ss(value);
    std::string item;

    while (std::getline(ss, item, ','))
    {
        item = trim(item);

        if (item.empty())
        {
            continue;
        }

        try
        {
            result.push_back(std::stoi(item));
        }
        catch (...)
        {
            std::cerr << "Invalid camera index in control file: " << item << "\n";
        }
    }

    return result;
}

EngineControl readControlFile(const EngineControl& fallback)
{
    std::ifstream file(CONTROL_FILE_PATH);

    if (!file.is_open())
    {
        return fallback;
    }

    EngineControl control = fallback;
    std::string line;

    while (std::getline(file, line))
    {
        line = trim(line);

        if (line.rfind("mode=", 0) == 0)
        {
            std::string mode = trim(line.substr(5));

            if (!mode.empty())
            {
                control.mode = mode;
            }
        }
        else if (line.rfind("cameras=", 0) == 0)
        {
            std::string camerasText = trim(line.substr(8));
            std::vector<int> parsed = parseCameraList(camerasText);

            if (!parsed.empty())
            {
                control.cameraIndexes = parsed;
            }
        }
    }

    return control;
}

void syncReaders(
    std::map<int, std::unique_ptr<CameraReader>>& readers,
    const std::vector<int>& requestedIndexes
)
{
    std::set<int> wanted(requestedIndexes.begin(), requestedIndexes.end());

    for (auto it = readers.begin(); it != readers.end();)
    {
        if (wanted.find(it->first) == wanted.end())
        {
            std::cout << "Closing camera index " << it->first << "\n";
            it->second->stop();
            it = readers.erase(it);
        }
        else
        {
            ++it;
        }
    }

    for (int index : requestedIndexes)
    {
        if (readers.find(index) != readers.end())
        {
            continue;
        }

        std::cout << "Adding camera index " << index << "\n";

        auto reader = std::make_unique<CameraReader>(index);

        if (!reader->start())
        {
            std::cerr << "Warning: camera " << index << " failed to start. Using black tile.\n";
            continue;
        }

        readers[index] = std::move(reader);
    }
}

int main(int argc, char** argv)
{
    if (argc < 3)
    {
        std::cerr << "Usage: video_engine.exe <mode> <camera_index_1> [camera_index_2] ...\n";
        std::cerr << "Example: video_engine.exe quad 0 1 2 3\n";
        return 1;
    }

    EngineControl activeControl;
    activeControl.mode = argv[1];

    for (int i = 2; i < argc; i++)
    {
        activeControl.cameraIndexes.push_back(std::stoi(argv[i]));
    }

    SharedFrameWriter sharedWriter;
    if (!sharedWriter.open())
    {
        std::cerr << "Failed to open shared frame writer\n";
        return 3;
    }

    std::map<int, std::unique_ptr<CameraReader>> readers;
    syncReaders(readers, activeControl.cameraIndexes);

    std::cout << "Started engine. Mode: " << activeControl.mode << "\n";
    std::cout << "Running continuous compositor. Press Ctrl+C to stop.\n";

    int frameCounter = 0;

    while (true)
    {
        if (frameCounter % 5 == 0)
        {
            EngineControl requestedControl = readControlFile(activeControl);

            bool modeChanged = requestedControl.mode != activeControl.mode;
            bool camerasChanged = requestedControl.cameraIndexes != activeControl.cameraIndexes;

            if (modeChanged || camerasChanged)
            {
                if (modeChanged)
                {
                    std::cout << "Layout mode changed to: " << requestedControl.mode << "\n";
                }

                if (camerasChanged)
                {
                    std::cout << "Camera selection changed. Syncing readers without full restart.\n";
                    syncReaders(readers, requestedControl.cameraIndexes);
                }

                activeControl = requestedControl;
            }
        }

        std::vector<cv::Mat> frames;
        int validFrameCount = 0;

        for (int index : activeControl.cameraIndexes)
        {
            cv::Mat frame;

            auto it = readers.find(index);

            if (
                it != readers.end() &&
                it->second->readLatest(frame) &&
                isNonBlack(frame)
            )
            {
                frames.push_back(frame);
                validFrameCount++;
            }
            else
            {
                frames.push_back(blank(OUTPUT_W, OUTPUT_H));
            }
        }

        cv::Mat finalOutput = composeFrames(frames, activeControl.mode);
        sharedWriter.writeBgrFrame(finalOutput);

        frameCounter++;

        if (frameCounter % 30 == 0)
        {
            std::cout << "Wrote shared frame. Cameras ready: "
                      << validFrameCount << "/"
                      << activeControl.cameraIndexes.size()
                      << ". Mode: "
                      << activeControl.mode
                      << "\n";
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(1000 / FPS));
    }

    for (auto& pair : readers)
    {
        pair.second->stop();
    }

    return 0;
}