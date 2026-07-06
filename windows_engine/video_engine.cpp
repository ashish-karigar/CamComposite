#include <opencv2/opencv.hpp>
#include <iostream>
#include <string>

static constexpr int OUTPUT_W = 1920;
static constexpr int OUTPUT_H = 1080;
static constexpr int FPS = 30;

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

    cv::VideoCapture cap(cameraIndex, cv::CAP_DSHOW);

    if (!cap.isOpened()) {
        std::cerr << "Failed to open camera index " << cameraIndex << "\n";
        return 1;
    }

    cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
    cap.set(cv::CAP_PROP_FRAME_WIDTH, OUTPUT_W);
    cap.set(cv::CAP_PROP_FRAME_HEIGHT, OUTPUT_H);
    cap.set(cv::CAP_PROP_FPS, FPS);

    std::cout << "Camera opened: " << cameraIndex << "\n";
    std::cout << "Actual: "
              << cap.get(cv::CAP_PROP_FRAME_WIDTH) << "x"
              << cap.get(cv::CAP_PROP_FRAME_HEIGHT) << "@"
              << cap.get(cv::CAP_PROP_FPS) << "\n";

    cv::Mat frame;
    cap >> frame;

    if (frame.empty()) {
        std::cerr << "No frame captured.\n";
        return 1;
    }

    cv::Mat composed = fitAndPad(frame, OUTPUT_W, OUTPUT_H);

    cv::imwrite("video_engine_output.png", composed);

    std::cout << "Saved video_engine_output.png\n";
    return 0;
}