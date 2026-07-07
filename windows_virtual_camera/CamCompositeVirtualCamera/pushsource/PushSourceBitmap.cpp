//------------------------------------------------------------------------------
// File: PushSourceBitmap.cpp
//
// Desc: Cam-Composite DirectShow virtual camera source.
//       Reads YUY2 frames from the CamComposite shared memory buffer.
//       Only outputs live frames when shared->broadcasting == 1.
//------------------------------------------------------------------------------

#include <streams.h>

#include "PushSource.h"
#include "PushGuids.h"
#include "../../shared/CamCompositeSharedFrame.h"

static const REFERENCE_TIME CAMCOMP_FRAME_TIME = 333333; // ~30 FPS

static HANDLE g_hSharedMap = NULL;
static CamCompositeSharedFrame* g_sharedFrame = NULL;

const AMOVIESETUP_MEDIATYPE sudOpPinTypes =
{
    &MEDIATYPE_Video,
    &MEDIASUBTYPE_YUY2
};

static void FillYuy2Black(BYTE* pData)
{
    if (!pData)
    {
        return;
    }

    // YUY2 black is not zero.
    // Each 2-pixel group is: Y0 U Y1 V = 16 128 16 128.
    for (LONG i = 0; i < CAMCOMP_FRAME_SIZE; i += 4)
    {
        pData[i + 0] = 16;
        pData[i + 1] = 128;
        pData[i + 2] = 16;
        pData[i + 3] = 128;
    }
}

static void CloseSharedFrame()
{
    if (g_sharedFrame)
    {
        UnmapViewOfFile(g_sharedFrame);
        g_sharedFrame = NULL;
    }

    if (g_hSharedMap)
    {
        CloseHandle(g_hSharedMap);
        g_hSharedMap = NULL;
    }
}

static bool EnsureSharedFrameOpen()
{
    if (g_sharedFrame != NULL)
    {
        return true;
    }

    g_hSharedMap = OpenFileMappingW(
        FILE_MAP_READ,
        FALSE,
        CAMCOMP_SHARED_MEMORY_NAME
    );

    if (!g_hSharedMap)
    {
        OutputDebugString(TEXT("[Cam-Composite] OpenFileMapping failed\n"));
        return false;
    }

    g_sharedFrame = static_cast<CamCompositeSharedFrame*>(
        MapViewOfFile(
            g_hSharedMap,
            FILE_MAP_READ,
            0,
            0,
            sizeof(CamCompositeSharedFrame)
        )
    );

    if (!g_sharedFrame)
    {
        OutputDebugString(TEXT("[Cam-Composite] MapViewOfFile failed\n"));
        CloseHandle(g_hSharedMap);
        g_hSharedMap = NULL;
        return false;
    }

    OutputDebugString(TEXT("[Cam-Composite] Shared frame opened\n"));
    return true;
}


/**********************************************
 *
 *  CPushPinBitmap Class
 *
 **********************************************/

CPushPinBitmap::CPushPinBitmap(HRESULT *phr, CSource *pFilter)
      : CSourceStream(NAME("Cam-Composite Stream"), phr, pFilter, L"Out"),
        m_FramesWritten(0),
        m_bZeroMemory(0),
        m_pBmi(0),
        m_cbBitmapInfo(0),
        m_hFile(INVALID_HANDLE_VALUE),
        m_pFile(NULL),
        m_pImage(NULL),
        m_iFrameNumber(0),
        m_rtFrameLength(CAMCOMP_FRAME_TIME)
{
    OutputDebugString(TEXT("[Cam-Composite] Constructor loaded\n"));

    if (phr)
    {
        *phr = S_OK;
    }
}


CPushPinBitmap::~CPushPinBitmap()
{
    DbgLog((LOG_TRACE, 3, TEXT("Frames written %d"), m_iFrameNumber));

    if (m_pFile)
    {
        delete [] m_pFile;
        m_pFile = NULL;
    }

    if (m_hFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(m_hFile);
        m_hFile = INVALID_HANDLE_VALUE;
    }
}


STDMETHODIMP CPushPinBitmap::NonDelegatingQueryInterface(REFIID riid, void **ppv)
{
    if (riid == IID_IKsPropertySet)
    {
        return GetInterface((IKsPropertySet *)this, ppv);
    }

    return CSourceStream::NonDelegatingQueryInterface(riid, ppv);
}


STDMETHODIMP CPushPinBitmap::Set(
    REFGUID guidPropSet,
    DWORD dwPropID,
    void *pInstanceData,
    DWORD cbInstanceData,
    void *pPropData,
    DWORD cbPropData
)
{
    return E_NOTIMPL;
}


STDMETHODIMP CPushPinBitmap::Get(
    REFGUID guidPropSet,
    DWORD dwPropID,
    void *pInstanceData,
    DWORD cbInstanceData,
    void *pPropData,
    DWORD cbPropData,
    DWORD *pcbReturned
)
{
    if (guidPropSet == AMPROPSETID_Pin && dwPropID == AMPROPERTY_PIN_CATEGORY)
    {
        if (pcbReturned)
        {
            *pcbReturned = sizeof(GUID);
        }

        if (pPropData == NULL)
        {
            return S_OK;
        }

        if (cbPropData < sizeof(GUID))
        {
            return E_UNEXPECTED;
        }

        *(GUID *)pPropData = PIN_CATEGORY_CAPTURE;
        return S_OK;
    }

    return E_PROP_ID_UNSUPPORTED;
}


STDMETHODIMP CPushPinBitmap::QuerySupported(
    REFGUID guidPropSet,
    DWORD dwPropID,
    DWORD *pTypeSupport
)
{
    if (guidPropSet == AMPROPSETID_Pin && dwPropID == AMPROPERTY_PIN_CATEGORY)
    {
        if (pTypeSupport)
        {
            *pTypeSupport = KSPROPERTY_SUPPORT_GET;
        }

        return S_OK;
    }

    return E_PROP_ID_UNSUPPORTED;
}


HRESULT CPushPinBitmap::GetMediaType(CMediaType *pMediaType)
{
    OutputDebugString(TEXT("[Cam-Composite] GetMediaType called\n"));

    CheckPointer(pMediaType, E_POINTER);

    VIDEOINFOHEADER *pvi = (VIDEOINFOHEADER *)pMediaType->AllocFormatBuffer(sizeof(VIDEOINFOHEADER));
    if (pvi == NULL)
    {
        return E_OUTOFMEMORY;
    }

    ZeroMemory(pvi, sizeof(VIDEOINFOHEADER));

    pvi->AvgTimePerFrame = m_rtFrameLength;

    pvi->bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    pvi->bmiHeader.biWidth = CAMCOMP_WIDTH;
    pvi->bmiHeader.biHeight = CAMCOMP_HEIGHT;
    pvi->bmiHeader.biPlanes = 1;
    pvi->bmiHeader.biBitCount = 16;
    pvi->bmiHeader.biCompression = MAKEFOURCC('Y', 'U', 'Y', '2');
    pvi->bmiHeader.biSizeImage = CAMCOMP_FRAME_SIZE;

    SetRectEmpty(&(pvi->rcSource));
    SetRectEmpty(&(pvi->rcTarget));

    pMediaType->SetType(&MEDIATYPE_Video);
    pMediaType->SetSubtype(&MEDIASUBTYPE_YUY2);
    pMediaType->SetFormatType(&FORMAT_VideoInfo);
    pMediaType->SetTemporalCompression(FALSE);
    pMediaType->SetSampleSize(CAMCOMP_FRAME_SIZE);

    return S_OK;
}


HRESULT CPushPinBitmap::DecideBufferSize(IMemAllocator *pAlloc, ALLOCATOR_PROPERTIES *pRequest)
{
    OutputDebugString(TEXT("[Cam-Composite] DecideBufferSize called\n"));

    CheckPointer(pAlloc, E_POINTER);
    CheckPointer(pRequest, E_POINTER);

    pRequest->cBuffers = 2;
    pRequest->cbBuffer = CAMCOMP_FRAME_SIZE;

    ALLOCATOR_PROPERTIES Actual;
    HRESULT hr = pAlloc->SetProperties(pRequest, &Actual);

    if (FAILED(hr))
    {
        return hr;
    }

    if (Actual.cbBuffer < CAMCOMP_FRAME_SIZE)
    {
        return E_FAIL;
    }

    return S_OK;
}


HRESULT CPushPinBitmap::FillBuffer(IMediaSample *pSample)
{
    BYTE *pData = NULL;
    long cbData = 0;

    CheckPointer(pSample, E_POINTER);

    HRESULT hr = pSample->GetPointer(&pData);
    if (FAILED(hr))
    {
        return hr;
    }

    cbData = pSample->GetSize();
    if (cbData < CAMCOMP_FRAME_SIZE)
    {
        return E_FAIL;
    }

    bool copiedFrame = false;

    if (EnsureSharedFrameOpen())
    {
        if (
            g_sharedFrame->magic == CAMCOMP_MAGIC &&
            g_sharedFrame->version == CAMCOMP_VERSION &&
            g_sharedFrame->width == CAMCOMP_WIDTH &&
            g_sharedFrame->height == CAMCOMP_HEIGHT &&
            g_sharedFrame->bytesPerPixel == CAMCOMP_BYTES_PER_PIXEL &&
            g_sharedFrame->frameSize == CAMCOMP_FRAME_SIZE &&
            g_sharedFrame->bufferCount == CAMCOMP_BUFFER_COUNT &&
            g_sharedFrame->broadcasting == 1 &&
            g_sharedFrame->frameIndex > 0
        )
        {
            LONG bufferIndex = g_sharedFrame->readableBufferIndex;

            if (bufferIndex >= 0 && bufferIndex < CAMCOMP_BUFFER_COUNT)
            {
                LONG beforeFrameIndex = g_sharedFrame->frameIndex;

                MemoryBarrier();

                CopyMemory(
                    pData,
                    g_sharedFrame->buffers[bufferIndex],
                    CAMCOMP_FRAME_SIZE
                );

                MemoryBarrier();

                LONG afterFrameIndex = g_sharedFrame->frameIndex;
                LONG afterBufferIndex = g_sharedFrame->readableBufferIndex;

                if (
                    beforeFrameIndex == afterFrameIndex &&
                    bufferIndex == afterBufferIndex
                )
                {
                    copiedFrame = true;
                }
                else
                {
                    bufferIndex = g_sharedFrame->readableBufferIndex;

                    if (bufferIndex >= 0 && bufferIndex < CAMCOMP_BUFFER_COUNT)
                    {
                        CopyMemory(
                            pData,
                            g_sharedFrame->buffers[bufferIndex],
                            CAMCOMP_FRAME_SIZE
                        );

                        copiedFrame = true;
                    }
                }
            }
        }
    }

    if (!copiedFrame)
    {
        FillYuy2Black(pData);
    }

    REFERENCE_TIME rtStart = m_iFrameNumber * m_rtFrameLength;
    REFERENCE_TIME rtStop = rtStart + m_rtFrameLength;

    pSample->SetTime(&rtStart, &rtStop);
    pSample->SetActualDataLength(CAMCOMP_FRAME_SIZE);
    pSample->SetSyncPoint(TRUE);

    m_iFrameNumber++;

    return S_OK;
}


/**********************************************
 *
 *  CPushSourceBitmap Class
 *
 **********************************************/

CPushSourceBitmap::CPushSourceBitmap(IUnknown *pUnk, HRESULT *phr)
           : CSource(NAME("Cam-Composite"), pUnk, CLSID_PushSourceBitmap)
{
    OutputDebugString(TEXT("[Cam-Composite] Filter created\n"));

    m_pPin = new CPushPinBitmap(phr, this);

    if (phr)
    {
        if (m_pPin == NULL)
        {
            *phr = E_OUTOFMEMORY;
        }
        else
        {
            *phr = S_OK;
        }
    }
}


CPushSourceBitmap::~CPushSourceBitmap()
{
    delete m_pPin;
    m_pPin = NULL;

    CloseSharedFrame();
}


CUnknown * WINAPI CPushSourceBitmap::CreateInstance(IUnknown *pUnk, HRESULT *phr)
{
    OutputDebugString(TEXT("[Cam-Composite] CreateInstance called\n"));

    CPushSourceBitmap *pNewFilter = new CPushSourceBitmap(pUnk, phr);

    if (phr)
    {
        if (pNewFilter == NULL)
        {
            *phr = E_OUTOFMEMORY;
        }
        else
        {
            *phr = S_OK;
        }
    }

    return pNewFilter;
}