[app]
title = CoC Command Center
package.name = coccommand
package.domain = org.cocvp
source.dir = .
source.include_exts = py,json,png,jpg,kv
version = 1.0
requirements = python3==3.11.9,hostpython3==3.11.9,kivy
orientation = portrait
fullscreen = 0
android.api = 35
android.minapi = 24
android.permissions = INTERNET,POST_NOTIFICATIONS,VIBRATE
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
