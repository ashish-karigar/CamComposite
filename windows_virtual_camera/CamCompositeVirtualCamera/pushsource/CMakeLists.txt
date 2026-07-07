cmake_minimum_required(VERSION 3.20)

project(CamCompositeVirtualCamera LANGUAGES CXX RC)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(CamCompositeVirtualCamera SHARED
    setup.cpp
    DibHelper.cpp
    PushSourceBitmap.cpp
    PushSource.rc
    PushSource.def
)

target_include_directories(CamCompositeVirtualCamera PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../baseclasses
)

target_sources(CamCompositeVirtualCamera PRIVATE
    ../../baseclasses/dllentry.cpp
    ../../baseclasses/dllsetup.cpp
    ../../baseclasses/arithutil.cpp
    ../../baseclasses/amfilter.cpp
    ../../baseclasses/amvideo.cpp
    ../../baseclasses/combase.cpp
    ../../baseclasses/ctlutil.cpp
    ../../baseclasses/mtype.cpp
    ../../baseclasses/outputq.cpp
    ../../baseclasses/pstream.cpp
    ../../baseclasses/pullpin.cpp
    ../../baseclasses/refclock.cpp
    ../../baseclasses/renbase.cpp
    ../../baseclasses/schedule.cpp
    ../../baseclasses/seekpt.cpp
    ../../baseclasses/source.cpp
    ../../baseclasses/strmctl.cpp
    ../../baseclasses/sysclock.cpp
    ../../baseclasses/transfrm.cpp
    ../../baseclasses/transip.cpp
    ../../baseclasses/vtrans.cpp
    ../../baseclasses/winctrl.cpp
    ../../baseclasses/winutil.cpp
    ../../baseclasses/wxdebug.cpp
    ../../baseclasses/wxlist.cpp
    ../../baseclasses/wxutil.cpp
)

target_compile_definitions(CamCompositeVirtualCamera PRIVATE
    WIN32
    NDEBUG
    _WINDOWS
    _USRDLL
    UNICODE
    _UNICODE
)

target_link_libraries(CamCompositeVirtualCamera PRIVATE
    strmiids
    winmm
    ole32
    oleaut32
    uuid
    user32
    gdi32
    advapi32
)

set_target_properties(CamCompositeVirtualCamera PROPERTIES
    OUTPUT_NAME "CamCompositeVirtualCamera"
)

target_link_options(CamCompositeVirtualCamera PRIVATE
    "/DEF:${CMAKE_CURRENT_SOURCE_DIR}/PushSource.def"
)