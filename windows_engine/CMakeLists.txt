cmake_minimum_required(VERSION 3.20)

project(CamCompositeWindowsEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(camera_discovery camera_discovery.cpp)

target_link_libraries(camera_discovery
    ole32
    oleaut32
    strmiids
)