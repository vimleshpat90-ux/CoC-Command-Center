# CoC Command Center — Python Android + Website Cloud Sync

This version adds Firebase Email/Password login and a shared Realtime Database. The Android app and `web/index.html` use the same Firebase user and data path.

## Before building
1. Create a Firebase project.
2. Enable **Authentication → Sign-in method → Email/Password**.
3. Create **Realtime Database**.
4. Put your Firebase Web App config into `firebase_config.json`.
5. Apply `firebase.rules.json` as the Realtime Database rules.

## Android build in Termux
```bash
pkg update -y
pkg install python git zip unzip -y
pip install --upgrade pip
pip install buildozer
cd CoC_Command_Center_Python
buildozer android debug
```
APK will be in `bin/`.

## Sync behavior
- Existing local data is preserved.
- On first login, if the cloud account has no data, local data can be uploaded.
- If both local and cloud data exist, the app compares `modified_at` and uses the newer copy.
- The app also attempts periodic sync while it is open.
- The same Firebase login works on the website.

## Important
Firebase credentials are project-specific. This package intentionally contains placeholders, so no one else can access your database. Do not send your Firebase service-account/private keys.
