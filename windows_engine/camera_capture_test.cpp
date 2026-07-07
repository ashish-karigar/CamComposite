#include <opencv2/opencv.hpp>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    int cameraIndex = 0;

    if (argc >= 2) {
        cameraIndex = std::stoi(argv[1]);
    }

    std::cout << "Opening camera index: " << cameraIndex << "\n";

    cv::VideoCapture cap(cameraIndex, cv::CAP_DSHOW);

    if (!cap.isOpened()) {
        std::cerr << "Failed to open camera.\n";
        return 1;
    }

    cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
    cap.set(cv::CAP_PROP_FRAME_WIDTH, 1920);
    cap.set(cv::CAP_PROP_FRAME_HEIGHT, 1080);
    cap.set(cv::CAP_PROP_FPS, 30);

    std::cout << "Actual width: " << cap.get(cv::CAP_PROP_FRAME_WIDTH) << "\n";
    std::cout << "Actual height: " << cap.get(cv::CAP_PROP_FRAME_HEIGHT) << "\n";
    std::cout << "Actual fps: " << cap.get(cv::CAP_PROP_FPS) << "\n";

    cv::Mat frame;

    for (int i = 0; i < 30; i++) {
        cap.read(frame);
    }

    if (frame.empty()) {
        std::cerr << "No frame captured.\n";
        return 1;
    }

    std::cout << "Captured frame: " << frame.cols << "x" << frame.rows << "\n";

    bool ok = cv::imwrite("capture_test_frame.png", frame);

    if (!ok) {
        std::cerr << "Failed to save frame.\n";
        return 1;
    }

    std::cout << "Saved capture_test_frame.png\n";

    cap.release();
    return 0;
}