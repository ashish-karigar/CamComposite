#define NOMINMAX
#include <windows.h>

#include <opencv2/opencv.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <filesystem>
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
static constexpr auto FRAME_INTERVAL = std::chrono::nanoseconds(1000000000LL / FPS);

static const std::string CONTROL_FILE_PATH = "runtime/control.txt";

struct EngineControl
{
    std::string mode;
    std::vector<int> cameraIndexes;
    bool broadcasting = false;
};

class SharedFrameWriter
{
private:
    HANDLE hMap = NULL;
    CamCompositeSharedFrame* shared = nullptr;

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
        shared->broadcasting = 0;

        std::cout << "Shared frame buffer ready with double buffering\n";
        std::cout << "Shared frame version: " << CAMCOMP_VERSION << "\n";
        return true;
    }

    void setBroadcasting(bool enabled)
    {
        if (!shared)
        {
            return;
        }

        shared->broadcasting = enabled ? 1 : 0;
        MemoryBarrier();
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

        // Wrap the inactive shared-memory buffer so OpenCV writes YUY2 into it
        // directly. OpenCV dispatches this conversion to its optimized SIMD
        // implementation, avoiding both the custom per-pixel loop and a copy.
        cv::Mat yuy2(
            CAMCOMP_HEIGHT,
            CAMCOMP_WIDTH,
            CV_8UC2,
            dst,
            CAMCOMP_WIDTH * CAMCOMP_BYTES_PER_PIXEL
        );
        cv::cvtColor(frame, yuy2, cv::COLOR_BGR2YUV_YUY2);

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

    void startAsync()
    {
        bool expected = false;
        if (!started.compare_exchange_strong(expected, true))
        {
            return;
        }

        running = true;
        worker = std::thread(&CameraReader::loop, this);
    }

    bool readLatest(cv::Mat& out, std::uint64_t& sequence)
    {
        std::lock_guard<std::mutex> lock(frameMutex);

        if (latestFrame.empty())
        {
            return false;
        }

        // cv::Mat is reference-counted. Taking a snapshot of the header keeps
        // the underlying camera frame alive without copying 6 MB while holding
        // the capture mutex. The producer replaces (rather than mutates) it.
        out = latestFrame;
        sequence = frameSequence;
        return true;
    }

    bool isReady() const
    {
        return ready.load();
    }

    bool hasFailed() const
    {
        return failed.load();
    }

    bool profileAndCache()
    {
        running = true;
        bool result = openCamera();
        running = false;
        if (cap.isOpened())
        {
            cap.release();
        }
        ready = false;
        return result;
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

        ready = false;
    }

    ~CameraReader()
    {
        stop();
    }

private:
    int cameraIndex;
    cv::VideoCapture cap;
    std::atomic<bool> started{false};
    std::atomic<bool> running{false};
    std::atomic<bool> ready{false};
    std::atomic<bool> failed{false};
    std::thread worker;
    std::mutex frameMutex;
    cv::Mat latestFrame;
    std::uint64_t frameSequence = 0;
    int failedReads = 0;
    bool ignoreCachedProfileOnce = false;

    struct CaptureProfile
    {
        int width;
        int height;
        int fps;
        int fourcc;
        const char* name;
    };

    bool configureProfile(const CaptureProfile& profile)
    {
        if (cap.isOpened())
        {
            cap.release();
        }

        cap.open(cameraIndex, cv::CAP_DSHOW);
        if (!cap.isOpened())
        {
            return false;
        }

        cap.set(cv::CAP_PROP_FOURCC, profile.fourcc);
        cap.set(cv::CAP_PROP_FRAME_WIDTH, profile.width);
        cap.set(cv::CAP_PROP_FRAME_HEIGHT, profile.height);
        cap.set(cv::CAP_PROP_FPS, profile.fps);
        cap.set(cv::CAP_PROP_BUFFERSIZE, 1);
        return true;
    }

    double measureProfile(
        const CaptureProfile& profile,
        bool& deliveredRequestedResolution,
        int warmupFrames,
        int measuredFrames
    )
    {
        deliveredRequestedResolution = false;
        if (!configureProfile(profile))
        {
            return 0.0;
        }

        cv::Mat frame;

        for (int i = 0; i < warmupFrames && running; i++)
        {
            if (!cap.read(frame) || frame.empty())
            {
                return 0.0;
            }
        }

        int successfulFrames = 0;
        auto started = std::chrono::steady_clock::now();

        for (int i = 0; i < measuredFrames && running; i++)
        {
            if (cap.read(frame) && !frame.empty())
            {
                successfulFrames++;
            }
        }

        double elapsedSeconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started
        ).count();

        if (!frame.empty())
        {
            deliveredRequestedResolution =
                frame.cols == profile.width && frame.rows == profile.height;
        }

        if (successfulFrames == 0 || elapsedSeconds <= 0.0)
        {
            return 0.0;
        }

        return static_cast<double>(successfulFrames) / elapsedSeconds;
    }

    std::filesystem::path profileCachePath() const
    {
        return std::filesystem::path("runtime") /
            ("camera_profile_" + std::to_string(cameraIndex) + ".txt");
    }

    int loadCachedProfileIndex(const CaptureProfile* profiles, int profileCount) const
    {
        std::ifstream file(profileCachePath());
        int width = 0;
        int height = 0;
        int fps = 0;
        int fourcc = 0;
        if (!(file >> width >> height >> fps >> fourcc))
        {
            return -1;
        }

        for (int i = 0; i < profileCount; i++)
        {
            if (
                profiles[i].width == width &&
                profiles[i].height == height &&
                profiles[i].fps == fps &&
                profiles[i].fourcc == fourcc
            )
            {
                return i;
            }
        }
        return -1;
    }

    void saveCachedProfile(const CaptureProfile& profile) const
    {
        std::error_code error;
        std::filesystem::create_directories("runtime", error);
        std::ofstream file(profileCachePath(), std::ios::trunc);
        if (file)
        {
            file << profile.width << " "
                 << profile.height << " "
                 << profile.fps << " "
                 << profile.fourcc << "\n";
            file.flush();
        }
    }

    bool openCamera()
    {
        if (cap.isOpened())
        {
            cap.release();
        }

        ready = false;
        failed = false;

        std::cout << "Opening camera index " << cameraIndex << " in background...\n";

        const int mjpg = cv::VideoWriter::fourcc('M', 'J', 'P', 'G');
        const int yuy2 = cv::VideoWriter::fourcc('Y', 'U', 'Y', '2');
        const CaptureProfile profiles[] = {
            {1920, 1080, 30, mjpg, "1080p30 MJPG"},
            {1280, 720, 30, mjpg, "720p30 MJPG"},
            {1920, 1080, 30, yuy2, "1080p30 YUY2"},
            {1280, 720, 30, yuy2, "720p30 YUY2"},
        };

        constexpr double MIN_ACCEPTABLE_FPS = 24.0;
        const int profileCount = static_cast<int>(sizeof(profiles) / sizeof(profiles[0]));
        int bestProfileIndex = -1;
        double bestMeasuredFps = 0.0;
        int cachedProfileIndex = ignoreCachedProfileOnce
            ? -1
            : loadCachedProfileIndex(profiles, profileCount);
        ignoreCachedProfileOnce = false;

        if (cachedProfileIndex >= 0)
        {
            if (configureProfile(profiles[cachedProfileIndex]))
            {
                std::cout << "Camera " << cameraIndex << " reused cached profile "
                          << profiles[cachedProfileIndex].name << " without reprofiling\n";
                return true;
            }

            std::cout << "Camera " << cameraIndex
                      << " cached profile could not open; probing alternatives.\n";
        }

        for (int i = 0; i < profileCount; i++)
        {
            if (i == cachedProfileIndex)
            {
                continue;
            }

            bool correctResolution = false;
            double measuredFps = measureProfile(profiles[i], correctResolution, 1, 8);

            std::cout << "Camera " << cameraIndex << " profile "
                      << profiles[i].name << ": measured "
                      << measuredFps << " FPS, delivered "
                      << cap.get(cv::CAP_PROP_FRAME_WIDTH) << "x"
                      << cap.get(cv::CAP_PROP_FRAME_HEIGHT)
                      << (correctResolution ? "" : " (resolution mismatch)")
                      << "\n";

            if (correctResolution && measuredFps > bestMeasuredFps)
            {
                bestProfileIndex = i;
                bestMeasuredFps = measuredFps;
            }

            if (correctResolution && measuredFps >= MIN_ACCEPTABLE_FPS)
            {
                saveCachedProfile(profiles[i]);
                std::cout << "Camera " << cameraIndex << " selected "
                          << profiles[i].name << "\n";
                return true;
            }
        }

        if (bestProfileIndex >= 0 && configureProfile(profiles[bestProfileIndex]))
        {
            saveCachedProfile(profiles[bestProfileIndex]);
            std::cout << "Camera " << cameraIndex << " selected best available profile "
                      << profiles[bestProfileIndex].name << " at measured "
                      << bestMeasuredFps << " FPS\n";
            return true;
        }

        std::cerr << "Failed to negotiate a usable format for camera index "
                  << cameraIndex << "\n";
        failed = true;
        return false;
    }

    void loop()
    {
        if (!openCamera())
        {
            running = false;
            return;
        }

        while (running)
        {
            cv::Mat frame;
            bool ok = cap.read(frame);

            if (ok && !frame.empty())
            {
                failedReads = 0;

                {
                    std::lock_guard<std::mutex> lock(frameMutex);
                    // Transfer shared ownership of this capture buffer. The next
                    // cap.read() uses a new local Mat, so readers get an immutable
                    // snapshot without a full-frame clone.
                    latestFrame = frame;
                    frameSequence++;
                }

                ready = true;
                failed = false;
            }
            else
            {
                failedReads++;

                if (failedReads >= 60)
                {
                    std::cerr << "Camera " << cameraIndex << " stalled. Reopening in background...\n";
                    ignoreCachedProfileOnce = true;
                    openCamera();
                    failedReads = 0;
                }

                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }

        if (cap.isOpened())
        {
            cap.release();
        }

        ready = false;
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

    // Preserve ownership isolation while avoiding a no-op full-frame resize.
    if (frame.cols == boxW && frame.rows == boxH)
    {
        return frame.clone();
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
void drawCameraNumber(cv::Mat& frame, int number, int x, int y)
{
    std::string text = std::to_string(number);

    int fontFace = cv::FONT_HERSHEY_DUPLEX;
    double fontScale = 0.95;
    int thickness = 2;

    // Soft shadow for readability without looking like a badge.
    cv::putText(
        frame,
        text,
        cv::Point(x + 2, y + 2),
        fontFace,
        fontScale,
        cv::Scalar(0, 0, 0),
        thickness + 2,
        cv::LINE_AA
    );

    // Clean white modern-looking number.
    cv::putText(
        frame,
        text,
        cv::Point(x, y),
        fontFace,
        fontScale,
        cv::Scalar(255, 255, 255),
        thickness,
        cv::LINE_AA
    );
}

void drawCameraNumbers(cv::Mat& frame, const std::string& mode, int count)
{
    const int w = frame.cols;
    const int h = frame.rows;
    const int pad = 34;

    if (mode == "single" || count == 1)
    {
        drawCameraNumber(frame, 1, pad, pad + 34);
        return;
    }

    if ((mode == "sbs" || mode == "side-by-side") && count >= 2)
    {
        drawCameraNumber(frame, 1, pad, pad + 34);
        drawCameraNumber(frame, 2, w / 2 + pad, pad + 34);
        return;
    }

    if (mode == "stacked" && count >= 2)
    {
        drawCameraNumber(frame, 1, pad, pad + 34);
        drawCameraNumber(frame, 2, pad, h / 2 + pad + 34);
        return;
    }

    if (mode == "pip" && count >= 2)
    {
        int pipW = OUTPUT_W / 4;
        int pipH = OUTPUT_H / 4;
        int margin = 40;
        int x = OUTPUT_W - pipW - margin;
        int y = OUTPUT_H - pipH - margin;

        drawCameraNumber(frame, 1, pad, pad + 34);
        drawCameraNumber(frame, 2, x + pad / 2, y + pad + 22);
        return;
    }

    if (mode == "triple" && count >= 3)
    {
        drawCameraNumber(frame, 1, pad, pad + 34);
        drawCameraNumber(frame, 2, pad, h / 2 + pad + 34);
        drawCameraNumber(frame, 3, w / 2 + pad, h / 2 + pad + 34);
        return;
    }

    if (mode == "quad" && count >= 4)
    {
        drawCameraNumber(frame, 1, pad, pad + 34);
        drawCameraNumber(frame, 2, w / 2 + pad, pad + 34);
        drawCameraNumber(frame, 3, pad, h / 2 + pad + 34);
        drawCameraNumber(frame, 4, w / 2 + pad, h / 2 + pad + 34);
    }
}
cv::Mat composeFrames(const std::vector<cv::Mat>& frames, const std::string& mode)
{
    if (frames.empty())
    {
        return blank(OUTPUT_W, OUTPUT_H);
    }

    if (mode == "single" || frames.size() == 1)
    {
        cv::Mat output = fitAndPad(frames[0], OUTPUT_W, OUTPUT_H);
        drawCameraNumbers(output, "single", 1);
        return output;
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
        drawCameraNumbers(output, "pip", 2);
        return output;
    }

    if ((mode == "sbs" || mode == "side-by-side") && frames.size() >= 2)
    {
        cv::Mat left = fitAndPad(frames[0], OUTPUT_W / 2, OUTPUT_H);
        cv::Mat right = fitAndPad(frames[1], OUTPUT_W / 2, OUTPUT_H);

        cv::Mat output;
        cv::hconcat(left, right, output);
        drawCameraNumbers(output, "sbs", 2);
        return output;
    }

    if (mode == "stacked" && frames.size() >= 2)
    {
        cv::Mat top = fitAndPad(frames[0], OUTPUT_W, OUTPUT_H / 2);
        cv::Mat bottom = fitAndPad(frames[1], OUTPUT_W, OUTPUT_H / 2);

        cv::Mat output;
        cv::vconcat(top, bottom, output);
        drawCameraNumbers(output, "stacked", 2);
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
        drawCameraNumbers(output, "triple", 3);
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
        drawCameraNumbers(output, "quad", 4);
        return output;
    }

    cv::Mat output = fitAndPad(frames[0], OUTPUT_W, OUTPUT_H);
    drawCameraNumbers(output, "single", 1);
    return output;
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
        else if (line.rfind("broadcasting=", 0) == 0)
        {
            std::string value = trim(line.substr(13));
            control.broadcasting = (value == "1" || value == "true" || value == "yes");
        }
        else if (line.rfind("broadcast=", 0) == 0)
        {
            std::string value = trim(line.substr(10));
            control.broadcasting = (value == "1" || value == "true" || value == "yes");
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

    for (int index : requestedIndexes)
    {
        if (readers.find(index) != readers.end())
        {
            continue;
        }

        std::cout << "Adding camera index " << index << " without blocking compositor\n";

        auto reader = std::make_unique<CameraReader>(index);
        reader->startAsync();

        readers[index] = std::move(reader);
    }

    for (auto it = readers.begin(); it != readers.end();)
    {
        if (wanted.find(it->first) == wanted.end())
        {
            std::cout << "Removing camera index " << it->first << " from layout\n";

            std::unique_ptr<CameraReader> removedReader = std::move(it->second);
            it = readers.erase(it);

            std::thread closer([reader = std::move(removedReader)]() mutable {
                reader->stop();
            });
            closer.detach();
        }
        else
        {
            ++it;
        }
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

    if (std::string(argv[1]) == "--profile")
    {
        bool allSucceeded = true;
        for (int i = 2; i < argc; i++)
        {
            int cameraIndex = std::stoi(argv[i]);
            std::cout << "Background profiling camera index " << cameraIndex << "\n";
            CameraReader reader(cameraIndex);
            if (!reader.profileAndCache())
            {
                allSucceeded = false;
            }
        }
        return allSucceeded ? 0 : 2;
    }

    EngineControl activeControl;
    activeControl.mode = argv[1];

    for (int i = 2; i < argc; i++)
    {
        activeControl.cameraIndexes.push_back(std::stoi(argv[i]));
    }

    activeControl.broadcasting = false;

    SharedFrameWriter sharedWriter;
    if (!sharedWriter.open())
    {
        std::cerr << "Failed to open shared frame writer\n";
        return 3;
    }

    sharedWriter.setBroadcasting(activeControl.broadcasting);

    std::map<int, std::unique_ptr<CameraReader>> readers;
    syncReaders(readers, activeControl.cameraIndexes);

    std::cout << "Started engine. Mode: " << activeControl.mode << "\n";
    std::cout << "Initial broadcasting: " << (activeControl.broadcasting ? "ON" : "OFF") << "\n";
    std::cout << "Running continuous compositor. Press Ctrl+C to stop.\n";

    std::uint64_t compositorTick = 0;
    std::uint64_t writtenFrameCount = 0;
    std::uint64_t droppedFrameSlots = 0;
    std::map<int, std::uint64_t> lastCameraSequences;
    bool forceCompose = true;
    auto nextFrameDeadline = std::chrono::steady_clock::now();

    while (true)
    {
        if (compositorTick % 5 == 0)
        {
            EngineControl requestedControl = readControlFile(activeControl);

            bool modeChanged = requestedControl.mode != activeControl.mode;
            bool camerasChanged = requestedControl.cameraIndexes != activeControl.cameraIndexes;
            bool broadcastingChanged = requestedControl.broadcasting != activeControl.broadcasting;

            if (modeChanged || camerasChanged || broadcastingChanged)
            {
                if (modeChanged)
                {
                    std::cout << "Layout mode changed to: " << requestedControl.mode << "\n";
                }

                if (camerasChanged)
                {
                    std::cout << "Camera selection changed. Syncing readers without blocking compositor.\n";
                    syncReaders(readers, requestedControl.cameraIndexes);
                }

                if (broadcastingChanged)
                {
                    std::cout << "Broadcasting changed to: "
                              << (requestedControl.broadcasting ? "ON" : "OFF")
                              << "\n";
                }

                activeControl = requestedControl;
                sharedWriter.setBroadcasting(activeControl.broadcasting);
                forceCompose = forceCompose || modeChanged || camerasChanged;
            }
        }

        std::vector<cv::Mat> frames;
        int validFrameCount = 0;
        bool hasNewCameraFrame = false;

        for (int index : activeControl.cameraIndexes)
        {
            cv::Mat frame;
            std::uint64_t sequence = 0;

            auto it = readers.find(index);

            if (
                it != readers.end() &&
                it->second->readLatest(frame, sequence)
            )
            {
                frames.push_back(frame);
                validFrameCount++;

                auto previous = lastCameraSequences.find(index);
                if (previous == lastCameraSequences.end() || previous->second != sequence)
                {
                    hasNewCameraFrame = true;
                    lastCameraSequences[index] = sequence;
                }
            }
            else
            {
                frames.push_back(blank(OUTPUT_W, OUTPUT_H));
            }
        }

        if (forceCompose || hasNewCameraFrame)
        {
            cv::Mat finalOutput = composeFrames(frames, activeControl.mode);
            sharedWriter.writeBgrFrame(finalOutput);
            forceCompose = false;
            writtenFrameCount++;

            if (writtenFrameCount % 30 == 0)
            {
                std::cout << "Wrote shared frame. Cameras ready: "
                          << validFrameCount << "/"
                          << activeControl.cameraIndexes.size()
                          << ". Mode: "
                          << activeControl.mode
                          << ". Broadcasting: "
                          << (activeControl.broadcasting ? "ON" : "OFF")
                          << ". Dropped pacing slots: "
                          << droppedFrameSlots
                          << "\n";
            }
        }

        compositorTick++;

        // Keep an absolute 30 FPS clock. When processing overruns, advance past
        // every missed slot instead of immediately running catch-up iterations.
        nextFrameDeadline += FRAME_INTERVAL;
        auto now = std::chrono::steady_clock::now();

        if (nextFrameDeadline > now)
        {
            std::this_thread::sleep_until(nextFrameDeadline);
        }
        else
        {
            const auto missedSlots =
                static_cast<std::uint64_t>((now - nextFrameDeadline) / FRAME_INTERVAL) + 1;
            droppedFrameSlots += missedSlots;
            nextFrameDeadline += FRAME_INTERVAL * missedSlots;
            std::this_thread::sleep_until(nextFrameDeadline);
        }
    }

    for (auto& pair : readers)
    {
        pair.second->stop();
    }

    return 0;
}
