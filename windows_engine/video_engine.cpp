#include <opencv2/opencv.hpp>
#include <atomic>
#include <chrono>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <filesystem>

static constexpr int OUTPUT_W = 1920;
static constexpr int OUTPUT_H = 1080;
static constexpr int FPS = 30;

class CameraReader {
public:
    CameraReader(int index) : cameraIndex(index) {}

    bool start() {
        if (!openCamera()) {
            std::cerr << "Failed to open camera index " << cameraIndex << "\n";
            return false;
        }

        running = true;
        worker = std::thread(&CameraReader::loop, this);
        return true;
    }

    bool readLatest(cv::Mat& out) {
        std::lock_guard<std::mutex> lock(frameMutex);

        if (latestFrame.empty()) {
            return false;
        }

        latestFrame.copyTo(out);
        return true;
    }

    void stop() {
        running = false;

        if (worker.joinable()) {
            worker.join();
        }

        if (cap.isOpened()) {
            cap.release();
        }
    }

    ~CameraReader() {
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

    bool openCamera() {
        if (cap.isOpened()) {
            cap.release();
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(300));

        std::cout << "Opening camera index " << cameraIndex << "...\n";

        cap.open(cameraIndex, cv::CAP_DSHOW);

        if (!cap.isOpened()) {
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

    void loop() {
        while (running) {
            cv::Mat frame;
            bool ok = cap.read(frame);

            if (ok && !frame.empty()) {
                failedReads = 0;

                std::lock_guard<std::mutex> lock(frameMutex);
                latestFrame = frame.clone();
            } else {
                failedReads++;

                if (failedReads >= 60) {
                    std::cerr << "Camera " << cameraIndex << " stalled. Reopening...\n";
                    openCamera();
                    failedReads = 0;
                }

                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
    }
};

cv::Mat blank(int w, int h) {
    return cv::Mat::zeros(h, w, CV_8UC3);
}

cv::Mat fitAndPad(const cv::Mat& frame, int boxW, int boxH) {
    if (frame.empty()) {
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

cv::Mat composeFrames(const std::vector<cv::Mat>& frames, const std::string& mode) {
    if (frames.empty()) {
        return blank(OUTPUT_W, OUTPUT_H);
    }

    if (mode == "single" || frames.size() == 1) {
        return fitAndPad(frames[0], OUTPUT_W, OUTPUT_H);
    }

    if ((mode == "sbs" || mode == "side-by-side") && frames.size() >= 2) {
        cv::Mat left = fitAndPad(frames[0], OUTPUT_W / 2, OUTPUT_H);
        cv::Mat right = fitAndPad(frames[1], OUTPUT_W / 2, OUTPUT_H);

        cv::Mat output;
        cv::hconcat(left, right, output);
        return output;
    }

    if (mode == "stacked" && frames.size() >= 2) {
        cv::Mat top = fitAndPad(frames[0], OUTPUT_W, OUTPUT_H / 2);
        cv::Mat bottom = fitAndPad(frames[1], OUTPUT_W, OUTPUT_H / 2);

        cv::Mat output;
        cv::vconcat(top, bottom, output);
        return output;
    }

    if (mode == "triple" && frames.size() >= 3) {
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

    if (mode == "quad" && frames.size() >= 4) {
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

bool isNonBlack(const cv::Mat& frame) {
    if (frame.empty()) return false;

    cv::Scalar meanValue = cv::mean(frame);
    double brightness = meanValue[0] + meanValue[1] + meanValue[2];

    return brightness > 15.0;
}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: video_engine.exe <mode> <camera_index_1> [camera_index_2] ...\n";
        std::cerr << "Example: video_engine.exe quad 0 1 2 3\n";
        return 1;
    }

    std::string mode = argv[1];

    std::vector<int> cameraIndexes;
    for (int i = 2; i < argc; i++) {
        cameraIndexes.push_back(std::stoi(argv[i]));
    }

    std::vector<std::unique_ptr<CameraReader>> readers;

    for (int index : cameraIndexes) {
        auto reader = std::make_unique<CameraReader>(index);
        if (!reader->start()) {
            std::cerr << "Warning: camera " << index << " failed to start. Using black tile.\n";
        }
        readers.push_back(std::move(reader));
    }

    std::cout << "Started " << readers.size() << " camera readers. Mode: " << mode << "\n";

    cv::Mat finalOutput;
    bool saved = false;

    for (int attempt = 0; attempt < 2000; attempt++) {
        std::vector<cv::Mat> frames;
        int validFrameCount = 0;

        for (auto& reader : readers) {
            cv::Mat frame;

            if (reader->readLatest(frame) && isNonBlack(frame)) {
                frames.push_back(frame);
                validFrameCount++;
            } else {
                frames.push_back(blank(OUTPUT_W, OUTPUT_H));
            }
        }

        finalOutput = composeFrames(frames, mode);

        if (validFrameCount == static_cast<int>(readers.size())) {
            std::cout << "Running continuous compositor. Press Ctrl+C to stop.\n";

            int frameCounter = 0;

            while (true) {
                std::vector<cv::Mat> frames;

                for (auto& reader : readers) {
                    cv::Mat frame;

                    if (reader->readLatest(frame) && isNonBlack(frame)) {
                        frames.push_back(frame);
                    } else {
                        frames.push_back(blank(OUTPUT_W, OUTPUT_H));
                    }
                }

                finalOutput = composeFrames(frames, mode);

                std::vector<int> jpgParams = {
                    cv::IMWRITE_JPEG_QUALITY, 95
                };

                cv::imwrite("cpp_latest_frame_tmp.jpg", finalOutput, jpgParams);

                try {
                    std::filesystem::remove("cpp_latest_frame.jpg");
                    std::filesystem::rename("cpp_latest_frame_tmp.jpg", "cpp_latest_frame.jpg");
                } catch (const std::exception& e) {
                    std::cerr << "Frame swap warning: " << e.what() << "\n";
                }

                frameCounter++;
                if (frameCounter % 30 == 0) {
                    std::cout << "Wrote cpp_latest_frame.jpg\n";
                }

                std::this_thread::sleep_for(std::chrono::milliseconds(66));
            }
        }

        if (attempt % 100 == 0) {
            std::cout << "Waiting for cameras: "
                      << validFrameCount << "/"
                      << readers.size()
                      << " ready\n";
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    for (auto& reader : readers) {
        reader->stop();
    }

    return 0;
}