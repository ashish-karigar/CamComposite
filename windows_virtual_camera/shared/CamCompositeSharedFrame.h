#pragma once

#include <windows.h>

#define CAMCOMP_SHARED_MEMORY_NAME L"Local\\CamCompositeFrameBuffer"

#define CAMCOMP_MAGIC 0x43434D50
#define CAMCOMP_VERSION 3

#define CAMCOMP_WIDTH 1920
#define CAMCOMP_HEIGHT 1080
#define CAMCOMP_BYTES_PER_PIXEL 2
#define CAMCOMP_FRAME_SIZE (CAMCOMP_WIDTH * CAMCOMP_HEIGHT * CAMCOMP_BYTES_PER_PIXEL)
#define CAMCOMP_BUFFER_COUNT 2

struct CamCompositeSharedFrame
{
    LONG magic;
    LONG version;

    LONG width;
    LONG height;
    LONG bytesPerPixel;
    LONG frameSize;
    LONG bufferCount;

    volatile LONG writing;
    volatile LONG readableBufferIndex;
    volatile LONG frameIndex;

    // 0 = preview-only mode. DirectShow outputs black frame to Zoom.
    // 1 = broadcast mode. DirectShow outputs real compositor frame to Zoom.
    volatile LONG broadcasting;

    BYTE buffers[CAMCOMP_BUFFER_COUNT][CAMCOMP_FRAME_SIZE];
};