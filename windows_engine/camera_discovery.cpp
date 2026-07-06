#include <windows.h>
#include <dshow.h>
#include <iostream>
#include <string>

#pragma comment(lib, "strmiids.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "oleaut32.lib")

std::string JsonEscape(const std::string& input) {
    std::string output;
    output.reserve(input.size());

    for (char c : input) {
        switch (c) {
            case '\\': output += "\\\\"; break;
            case '"': output += "\\\""; break;
            case '\n': output += "\\n"; break;
            case '\r': output += "\\r"; break;
            case '\t': output += "\\t"; break;
            default: output += c; break;
        }
    }

    return output;
}

std::string WideToUtf8(const std::wstring& wide) {
    if (wide.empty()) return "";

    int sizeNeeded = WideCharToMultiByte(
        CP_UTF8,
        0,
        wide.c_str(),
        -1,
        nullptr,
        0,
        nullptr,
        nullptr
    );

    std::string result(sizeNeeded - 1, 0);

    WideCharToMultiByte(
        CP_UTF8,
        0,
        wide.c_str(),
        -1,
        result.data(),
        sizeNeeded,
        nullptr,
        nullptr
    );

    return result;
}

int main() {
    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(hr)) {
        std::cerr << "COM init failed\n";
        return 1;
    }

    ICreateDevEnum* devEnum = nullptr;
    IEnumMoniker* enumMoniker = nullptr;

    hr = CoCreateInstance(
        CLSID_SystemDeviceEnum,
        nullptr,
        CLSCTX_INPROC_SERVER,
        IID_ICreateDevEnum,
        reinterpret_cast<void**>(&devEnum)
    );

    if (FAILED(hr) || !devEnum) {
        std::cerr << "Failed to create device enum\n";
        CoUninitialize();
        return 1;
    }

    hr = devEnum->CreateClassEnumerator(
        CLSID_VideoInputDeviceCategory,
        &enumMoniker,
        0
    );

    if (hr != S_OK || !enumMoniker) {
        std::cout << "[]\n";
        devEnum->Release();
        CoUninitialize();
        return 0;
    }

    std::cout << "[\n";

    IMoniker* moniker = nullptr;
    ULONG fetched = 0;
    int index = 0;
    bool first = true;

    while (enumMoniker->Next(1, &moniker, &fetched) == S_OK) {
        IPropertyBag* propBag = nullptr;

        hr = moniker->BindToStorage(
            nullptr,
            nullptr,
            IID_IPropertyBag,
            reinterpret_cast<void**>(&propBag)
        );

        std::string name = "Unknown Camera";
        std::string devicePath = "";

        if (SUCCEEDED(hr) && propBag) {
            VARIANT varName;
            VariantInit(&varName);

            if (SUCCEEDED(propBag->Read(L"FriendlyName", &varName, nullptr))) {
                name = WideToUtf8(varName.bstrVal);
            }

            VariantClear(&varName);
            propBag->Release();
        }

        LPOLESTR displayName = nullptr;
        if (SUCCEEDED(moniker->GetDisplayName(nullptr, nullptr, &displayName))) {
            devicePath = WideToUtf8(displayName);
            CoTaskMemFree(displayName);
        }

        if (!first) {
            std::cout << ",\n";
        }

        if (
            name.find("Unity") != std::string::npos ||
            name.find("Virtual") != std::string::npos
        ) {
            moniker->Release();
            continue;
        }

        std::cout << "  {\n";
        std::cout << "    \"id\": " << index << ",\n";
        std::cout << "    \"name\": \"" << JsonEscape(name) << "\",\n";
        std::cout << "    \"device_path\": \"" << JsonEscape(devicePath) << "\",\n";
        std::cout << "    \"preview_index\": " << index << "\n";
        std::cout << "  }";

        first = false;
        index++;

        moniker->Release();
    }

    std::cout << "\n]\n";

    enumMoniker->Release();
    devEnum->Release();
    CoUninitialize();

    return 0;
}