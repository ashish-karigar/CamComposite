#include <opencv2/opencv.hpp>
#include <atomic>
#include <chrono>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>

static constexpr int OUTPUT_W = 1920;
static constexpr int OUTPUT_H = 1080;
static constexpr int FPS = 30;

class CameraReader {
int failedReads = 0;
public:
    CameraReader(int index) : cameraIndex(index) {}

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

        return true;
    }

    bool start() {
        if (!openCamera()) {
            std::cerr << "Failed to open camera index " << cameraIndex << "\n";
            return false;
        }

        if (!cap.isOpened()) {
            std::cerr << "Failed to open camera index " << cameraIndex << "\n";
            return false;
        }

        cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
        cap.set(cv::CAP_PROP_FRAME_WIDTH, OUTPUT_W);
        cap.set(cv::CAP_PROP_FRAME_HEIGHT, OUTPUT_H);
        cap.set(cv::CAP_PROP_FPS, FPS);

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
                    std::cerr << "Camera stalled. Reopening camera...\n";
                    openCamera();
                    failedReads = 0;
                }

                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
    }
};

cv::Mat fitAndPad(const cv::Mat& frame, int boxW, int boxH) {
    if (frame.empty()) {
        return cv::Mat::zeros(boxH, boxW, CV_8UC3);
    }

    double scale = std::min(
        static_cast<double>(boxW) / frame.cols,
        static_cast<double>(boxH) / frame.rows
    );

    int newW = std::max(1, static_cast<int>(frame.cols * scale));
    int newH = std::max(1, static_cast<int>(frame.rows * scale));

    cv::Mat resized;
    cv::resize(frame, resized, cv::Size(newW, newH), 0, 0, cv::INTER_AREA);

    cv::Mat canvas = cv::Mat::zeros(boxH, boxW, CV_8UC3);

    int x = (boxW - newW) / 2;
    int y = (boxH - newH) / 2;

    resized.copyTo(canvas(cv::Rect(x, y, newW, newH)));
    return canvas;
}

int main(int argc, char** argv) {
    int cameraIndex = 0;

    if (argc >= 2) {
        cameraIndex = std::stoi(argv[1]);
    }

    CameraReader reader(cameraIndex);

    if (!reader.start()) {
        return 1;
    }

    std::cout << "Continuous reader started for camera index " << cameraIndex << "\n";

    cv::Mat frame;
    bool saved = false;

    for (int i = 0; i < 1500; i++) {
    if (reader.readLatest(frame)) {
        cv::Scalar meanValue = cv::mean(frame);
        double brightness = meanValue[0] + meanValue[1] + meanValue[2];

        if (brightness > 15.0) {
            cv::Mat composed = fitAndPad(frame, OUTPUT_W, OUTPUT_H);
            cv::imwrite("video_engine_live_output.png", composed);
            std::cout << "Saved video_engine_live_output.png\n";
            saved = true;
            break;
        }
    }

    std::this_thread::sleep_for(std::chrono::milliseconds(10));
}

    reader.stop();

    if (!saved) {
        std::cerr << "No valid frame received from threaded reader.\n";
        return 1;
    }

    return 0;
}