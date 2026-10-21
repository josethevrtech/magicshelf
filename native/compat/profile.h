#pragma once
// Both devices share the renderer and interaction code, but have separate
// process locks, settings, registrations, captures, and model assets.
#ifdef ANDROID_PHONE
constexpr bool AndroidOnly=true;
constexpr const char* ApplicationKey="local.androidphone.vr";
constexpr const char* DeviceKey="local.androidphone.device";
constexpr const char* AppTitle="Android Phone";
constexpr const char* ManifestFile="androidphone.vrmanifest";
constexpr const char* SettingsFile="android-settings.json";
constexpr const char* LockFile="android-instance.lock";
constexpr const char* IconFile="android-phone-icon.png";
constexpr const char* AssetDirectory="assets/android-phone";
constexpr int ScreenWidth=720,ScreenHeight=1600;
constexpr float ScreenX=.0355f,ScreenY=ScreenX*ScreenHeight/ScreenWidth;
constexpr float ScreenCY=.0015f,ScreenZ=.00431f,PhonePlaneWidth=.202f;
constexpr float BodyX=.0385f,BodyY=.0875f,HomeY=-.0827f;
constexpr float HomeHalfX=.018f,HomeHalfY=.0038f,DefaultSize=2.2f;
constexpr int RenderWidth=3072,RenderHeight=1536;
#else
constexpr bool AndroidOnly=false;
constexpr const char* ApplicationKey="local.digitalpartner.vr";
constexpr const char* DeviceKey="local.digitalpartner.device";
constexpr const char* AppTitle="Digital Partner";
constexpr const char* ManifestFile="digitalpartner.vrmanifest";
constexpr const char* SettingsFile="settings.json";
constexpr const char* LockFile="instance.lock";
constexpr const char* IconFile="season1-icon.png";
constexpr const char* AssetDirectory="assets";
constexpr int ScreenWidth=480,ScreenHeight=1046;
constexpr float ScreenY=.0825f,ScreenX=ScreenY*ScreenWidth/ScreenHeight;
constexpr float ScreenCY=.0132f,ScreenZ=.0034925f,PhonePlaneWidth=.272f;
constexpr float BodyX=.066275f,BodyY=.1144f,HomeY=-.0935f;
constexpr float HomeHalfX=.020f,HomeHalfY=.014f,DefaultSize=1.6f;
constexpr int RenderWidth=2048,RenderHeight=1024;
#endif
constexpr int SettingsWidth=480,SettingsHeight=1046;
