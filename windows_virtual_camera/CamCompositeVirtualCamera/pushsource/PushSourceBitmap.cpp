//------------------------------------------------------------------------------
// File: PushSourceBitmap.cpp
//
// Desc: Cam-Composite DirectShow virtual camera test source.
//------------------------------------------------------------------------------

#include <streams.h>

#include "PushSource.h"
#include "PushGuids.h"

static const LONG CAMCOMP_WIDTH = 1920;
static const LONG CAMCOMP_HEIGHT = 1080;
static const LONG CAMCOMP_BYTES_PER_PIXEL = 2;
static const LONG CAMCOMP_IMAGE_SIZE = CAMCOMP_WIDTH * CAMCOMP_HEIGHT * CAMCOMP_BYTES_PER_PIXEL;
static const REFERENCE_TIME CAMCOMP_FRAME_TIME = 333333; // ~30 FPS

const AMOVIESETUP_MEDIATYPE sudOpPinTypes =
{
    &MEDIATYPE_Video,
    &MEDIASUBTYPE_RGB24
};


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

    if (phr) {
        *phr = S_OK;
    }
}


CPushPinBitmap::~CPushPinBitmap()
{
    DbgLog((LOG_TRACE, 3, TEXT("Frames written %d"), m_iFrameNumber));

    if (m_pFile) {
        delete [] m_pFile;
        m_pFile = NULL;
    }

    if (m_hFile != INVALID_HANDLE_VALUE) {
        CloseHandle(m_hFile);
        m_hFile = INVALID_HANDLE_VALUE;
    }
}

STDMETHODIMP CPushPinBitmap::NonDelegatingQueryInterface(REFIID riid, void **ppv)
{
    if (riid == IID_IKsPropertySet) {
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
    if (guidPropSet == AMPROPSETID_Pin && dwPropID == AMPROPERTY_PIN_CATEGORY) {
        if (pcbReturned) {
            *pcbReturned = sizeof(GUID);
        }

        if (pPropData == NULL) {
            return S_OK;
        }

        if (cbPropData < sizeof(GUID)) {
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
    if (guidPropSet == AMPROPSETID_Pin && dwPropID == AMPROPERTY_PIN_CATEGORY) {
        if (pTypeSupport) {
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
    if (pvi == NULL) {
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
    pvi->bmiHeader.biSizeImage = CAMCOMP_IMAGE_SIZE;

    SetRectEmpty(&(pvi->rcSource));
    SetRectEmpty(&(pvi->rcTarget));

    pMediaType->SetType(&MEDIATYPE_Video);
    pMediaType->SetSubtype(&MEDIASUBTYPE_YUY2);
    pMediaType->SetFormatType(&FORMAT_VideoInfo);
    pMediaType->SetTemporalCompression(FALSE);
    pMediaType->SetSampleSize(CAMCOMP_IMAGE_SIZE);

    return S_OK;
}


HRESULT CPushPinBitmap::DecideBufferSize(IMemAllocator *pAlloc, ALLOCATOR_PROPERTIES *pRequest)
{
    OutputDebugString(TEXT("[Cam-Composite] DecideBufferSize called\n"));

    CheckPointer(pAlloc, E_POINTER);
    CheckPointer(pRequest, E_POINTER);

    pRequest->cBuffers = 1;
    pRequest->cbBuffer = CAMCOMP_IMAGE_SIZE;

    ALLOCATOR_PROPERTIES Actual;
    HRESULT hr = pAlloc->SetProperties(pRequest, &Actual);

    if (FAILED(hr)) {
        return hr;
    }

    if (Actual.cbBuffer < CAMCOMP_IMAGE_SIZE) {
        return E_FAIL;
    }

    return S_OK;
}


HRESULT CPushPinBitmap::FillBuffer(IMediaSample *pSample)
{
    OutputDebugString(TEXT("[Cam-Composite] FillBuffer called\n"));

    BYTE *pData = NULL;
    long cbData = 0;

    CheckPointer(pSample, E_POINTER);

    HRESULT hr = pSample->GetPointer(&pData);
    if (FAILED(hr)) {
        return hr;
    }

    cbData = pSample->GetSize();
    if (cbData < CAMCOMP_IMAGE_SIZE) {
        return E_FAIL;
    }

    const int squareSize = 120;
    const int squareX = (m_iFrameNumber * 12) % (CAMCOMP_WIDTH - squareSize);
    const int squareY = CAMCOMP_HEIGHT / 2 - squareSize / 2;

    for (LONG y = 0; y < CAMCOMP_HEIGHT; y++) {
        BYTE *row = pData + (y * CAMCOMP_WIDTH * CAMCOMP_BYTES_PER_PIXEL);

        for (LONG x = 0; x < CAMCOMP_WIDTH; x += 2) {
            BYTE y0 = 80;
            BYTE y1 = 80;
            BYTE u = 128;
            BYTE v = 128;

            int bar = (x * 8) / CAMCOMP_WIDTH;

            switch (bar) {
                case 0: y0 = y1 = 235; u = 128; v = 128; break; // white
                case 1: y0 = y1 = 210; u = 16;  v = 146; break; // yellow-ish
                case 2: y0 = y1 = 170; u = 166; v = 16;  break; // cyan-ish
                case 3: y0 = y1 = 145; u = 54;  v = 34;  break; // green-ish
                case 4: y0 = y1 = 105; u = 202; v = 222; break; // magenta-ish
                case 5: y0 = y1 = 80;  u = 90;  v = 240; break; // red-ish
                case 6: y0 = y1 = 41;  u = 240; v = 110; break; // blue-ish
                default: y0 = y1 = 30; u = 128; v = 128; break;
            }

            if (
                x >= squareX && x < squareX + squareSize &&
                y >= squareY && y < squareY + squareSize
            ) {
                y0 = 235;
                y1 = 235;
                u = 128;
                v = 128;
            }

            row[x * 2 + 0] = y0;
            row[x * 2 + 1] = u;
            row[x * 2 + 2] = y1;
            row[x * 2 + 3] = v;
        }
    }

    REFERENCE_TIME rtStart = m_iFrameNumber * m_rtFrameLength;
    REFERENCE_TIME rtStop = rtStart + m_rtFrameLength;

    pSample->SetTime(&rtStart, &rtStop);
    pSample->SetActualDataLength(CAMCOMP_IMAGE_SIZE);
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

    if (phr) {
        if (m_pPin == NULL) {
            *phr = E_OUTOFMEMORY;
        } else {
            *phr = S_OK;
        }
    }
}


CPushSourceBitmap::~CPushSourceBitmap()
{
    delete m_pPin;
    m_pPin = NULL;
}


CUnknown * WINAPI CPushSourceBitmap::CreateInstance(IUnknown *pUnk, HRESULT *phr)
{
    OutputDebugString(TEXT("[Cam-Composite] CreateInstance called\n"));

    CPushSourceBitmap *pNewFilter = new CPushSourceBitmap(pUnk, phr);

    if (phr) {
        if (pNewFilter == NULL) {
            *phr = E_OUTOFMEMORY;
        } else {
            *phr = S_OK;
        }
    }

    return pNewFilter;
}