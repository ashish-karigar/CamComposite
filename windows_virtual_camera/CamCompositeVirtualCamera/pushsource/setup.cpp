//------------------------------------------------------------------------------
// File: Setup.cpp
//
// Desc: DirectShow sample code - implementation of PushSource sample filters
//
// Copyright (c)  Microsoft Corporation.  All rights reserved.
//------------------------------------------------------------------------------

#include <streams.h>
#include <initguid.h>
#include <dshow.h>

#include "PushGuids.h"
#include "PushSource.h"

// Note: It is better to register no media types than to register a partial 
// media type (subtype == GUID_NULL) because that can slow down intelligent connect 
// for everyone else.

// For a specialized source filter like this, it is best to leave out the 
// AMOVIESETUP_FILTER altogether, so that the filter is not available for 
// intelligent connect. Instead, use the CLSID to create the filter or just 
// use 'new' in your application.


// Filter setup data
const AMOVIESETUP_MEDIATYPE sudOpPinTypes =
{
    &MEDIATYPE_Video,
    &MEDIASUBTYPE_YUY2
};

const AMOVIESETUP_PIN sudOutputPinBitmap = 
{
    L"Output",      // Obsolete, not used.
    FALSE,          // Is this pin rendered?
    TRUE,           // Is it an output pin?
    FALSE,          // Can the filter create zero instances?
    FALSE,          // Does the filter create multiple instances?
    &CLSID_NULL,    // Obsolete.
    NULL,           // Obsolete.
    1,              // Number of media types.
    &sudOpPinTypes  // Pointer to media types.
};

const AMOVIESETUP_FILTER sudPushSourceBitmap =
{
    &CLSID_PushSourceBitmap,        // Filter CLSID
    g_wszPushBitmap,                // String name
    MERIT_PREFERRED,                // Filter merit
    1,                              // Number pins
    &sudOutputPinBitmap             // Pin details
};


const AMOVIESETUP_PIN sudOutputPinBitmapSet = 
{
    L"Output",      // Obsolete, not used.
    FALSE,          // Is this pin rendered?
    TRUE,           // Is it an output pin?
    FALSE,          // Can the filter create zero instances?
    FALSE,          // Does the filter create multiple instances?
    &CLSID_NULL,    // Obsolete.
    NULL,           // Obsolete.
    1,              // Number of media types.
    &sudOpPinTypes  // Pointer to media types.
};

const REGPINTYPES sudRegPinTypes =
{
    &MEDIATYPE_Video,
    &MEDIASUBTYPE_YUY2
};

const REGFILTERPINS sudRegOutputPin =
{
    L"Output",          // Pin name
    FALSE,              // Rendered
    TRUE,               // Output pin
    FALSE,              // Zero instances
    FALSE,              // Multiple instances
    NULL,               // Connects to any filter
    NULL,               // Connects to any pin
    1,                  // Media type count
    &sudRegPinTypes     // Media types
};

const AMOVIESETUP_FILTER sudPushSourceBitmapSet =
{
    &CLSID_PushSourceBitmapSet,// Filter CLSID
    g_wszPushBitmapSet,        // String name
    MERIT_DO_NOT_USE,          // Filter merit
    1,                         // Number pins
    &sudOutputPinBitmapSet     // Pin details
};


const AMOVIESETUP_PIN sudOutputPinDesktop = 
{
    L"Output",      // Obsolete, not used.
    FALSE,          // Is this pin rendered?
    TRUE,           // Is it an output pin?
    FALSE,          // Can the filter create zero instances?
    FALSE,          // Does the filter create multiple instances?
    &CLSID_NULL,    // Obsolete.
    NULL,           // Obsolete.
    1,              // Number of media types.
    &sudOpPinTypes  // Pointer to media types.
};

const AMOVIESETUP_FILTER sudPushSourceDesktop =
{
    &CLSID_PushSourceDesktop,// Filter CLSID
    g_wszPushDesktop,       // String name
    MERIT_DO_NOT_USE,       // Filter merit
    1,                      // Number pins
    &sudOutputPinDesktop    // Pin details
};


// List of class IDs and creator functions for the class factory. This
// provides the link between the OLE entry point in the DLL and an object
// being created. The class factory will call the static CreateInstance.
// We provide a set of filters in this one DLL.

CFactoryTemplate g_Templates[1] = 
{
    { 
      g_wszPushBitmap,                // Name
      &CLSID_PushSourceBitmap,        // CLSID
      CPushSourceBitmap::CreateInstance,  // Method to create an instance of MyComponent
      NULL,                           // Initialization function
      &sudPushSourceBitmap            // Set-up information (for filters)
    },
};

int g_cTemplates = sizeof(g_Templates) / sizeof(g_Templates[0]);    



////////////////////////////////////////////////////////////////////////
//
// Exported entry points for registration and unregistration 
// (in this case they only call through to default implementations).
//
////////////////////////////////////////////////////////////////////////

STDAPI DllRegisterServer()
{
    HRESULT hr = AMovieDllRegisterServer2(TRUE);
    if (FAILED(hr)) {
        return hr;
    }

    IFilterMapper2* pFM = NULL;
    hr = CoCreateInstance(
        CLSID_FilterMapper2,
        NULL,
        CLSCTX_INPROC_SERVER,
        IID_IFilterMapper2,
        (void**)&pFM
    );

    if (FAILED(hr)) {
        return hr;
    }

    REGFILTER2 rf2;
    rf2.dwVersion = 1;
    rf2.dwMerit = MERIT_PREFERRED;
    rf2.cPins = 1;
    rf2.rgPins = &sudRegOutputPin;

    hr = pFM->RegisterFilter(
        CLSID_PushSourceBitmap,
        g_wszPushBitmap,
        NULL,
        &CLSID_VideoInputDeviceCategory,
        NULL,
        &rf2
    );

    pFM->Release();
    return hr;
}

STDAPI DllUnregisterServer()
{
    IFilterMapper2* pFM = NULL;
    HRESULT hr = CoCreateInstance(
        CLSID_FilterMapper2,
        NULL,
        CLSCTX_INPROC_SERVER,
        IID_IFilterMapper2,
        (void**)&pFM
    );

    if (SUCCEEDED(hr)) {
        pFM->UnregisterFilter(
            &CLSID_VideoInputDeviceCategory,
            NULL,
            CLSID_PushSourceBitmap
        );
        pFM->Release();
    }

    return AMovieDllRegisterServer2(FALSE);
}

//
// DllEntryPoint
//
extern "C" BOOL WINAPI DllEntryPoint(HINSTANCE, ULONG, LPVOID);

BOOL APIENTRY DllMain(HANDLE hModule, 
                      DWORD  dwReason, 
                      LPVOID lpReserved)
{
	return DllEntryPoint((HINSTANCE)(hModule), dwReason, lpReserved);
}

