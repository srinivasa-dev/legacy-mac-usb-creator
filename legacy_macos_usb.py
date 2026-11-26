#!/usr/bin/env python3
"""
legacy_macos_usb.py
Production-grade CLI tool to assemble and create authentic, bootable legacy
macOS USB installers on modern Apple Silicon and Intel Macs without triggering
AMFI Killed: 9 crashes or installer package distribution blocks.

Repository: https://github.com/srinivasa-dev/legacy-mac-usb-creator
License: Apache-2.0
"""

import argparse
import os
import plistlib
import shutil
import subprocess
import sys

DEFAULT_SOURCE_DIR = "/private/tmp/com.ninxsoft.mist/041-91758"
DEFAULT_DEST_APP = "/Applications/Install macOS High Sierra.app"
DEFAULT_TARGET_VOLUME = "/Volumes/MyVolume"

REQUIRED_FILES = [
    "BaseSystem.dmg",
    "BaseSystem.chunklist",
    "InstallESDDmg.pkg",
    "InstallInfo.plist",
    "AppleDiagnostics.dmg",
    "AppleDiagnostics.chunklist"
]


def check_root():
    if os.geteuid() != 0:
        print("\033[91m[ERROR] This utility requires superuser privileges.\033[0m")
        print("Please run with sudo:")
        print("  sudo python3 legacy_macos_usb.py --volume /Volumes/MyVolume")
        sys.exit(1)


def unmount_stale_volumes():
    stale_mounts = [
        "/Volumes/OS X Base System",
        "/Volumes/041-91758",
        "/Volumes/InstallESD"
    ]
    for mount in stale_mounts:
        if os.path.exists(mount):
            print(f"  Detaching leftover mount: {mount}")
            subprocess.run(["hdiutil", "detach", mount, "-force"], capture_output=True)


def extract_installer_app(source_dir: str, dest_app: str):
    print("\n\033[96m=== Step 1: Extracting Installer Application ===\033[0m")
    base_system_dmg = os.path.join(source_dir, "BaseSystem.dmg")
    if not os.path.exists(base_system_dmg):
        print(f"\033[91m[ERROR] BaseSystem.dmg not found in {source_dir}\033[0m")
        sys.exit(1)

    unmount_stale_volumes()

    print(f"Mounting {base_system_dmg}...")
    mount_res = subprocess.run(
        ["hdiutil", "attach", base_system_dmg, "-nobrowse", "-noverify"],
        capture_output=True,
        text=True
    )
    if mount_res.returncode != 0:
        print(f"\033[91m[ERROR] Failed to attach {base_system_dmg}: {mount_res.stderr}\033[0m")
        sys.exit(1)

    mount_point = "/Volumes/OS X Base System"
    if not os.path.exists(mount_point):
        for line in mount_res.stdout.splitlines():
            parts = line.strip().split("\t")
            for part in parts:
                p = part.strip()
                if os.path.isdir(p) and "Base System" in p:
                    mount_point = p
                    break

    app_source = None
    for item in os.listdir(mount_point):
        if item.endswith(".app"):
            app_source = os.path.join(mount_point, item)
            break

    if not app_source:
        print(f"\033[91m[ERROR] No .app bundle found inside {mount_point}\033[0m")
        subprocess.run(["hdiutil", "detach", mount_point, "-force"])
        sys.exit(1)

    print(f"Copying {app_source} -> {dest_app}...")
    if os.path.exists(dest_app):
        shutil.rmtree(dest_app)

    subprocess.run(["cp", "-R", app_source, dest_app], check=True)
    print("Detaching BaseSystem volume...")
    subprocess.run(["hdiutil", "detach", mount_point, "-force"], capture_output=True)
    print("\033[92m✓ Installer application extracted successfully.\033[0m")


def assemble_shared_support(source_dir: str, dest_app: str):
    print("\n\033[96m=== Step 2: Assembling SharedSupport Payload ===\033[0m")
    shared_support = os.path.join(dest_app, "Contents", "SharedSupport")
    os.makedirs(shared_support, exist_ok=True)

    for filename in REQUIRED_FILES:
        src = os.path.join(source_dir, filename)
        dest_filename = "InstallESD.dmg" if filename == "InstallESDDmg.pkg" else filename
        dest = os.path.join(shared_support, dest_filename)
        print(f"  Copying {filename} -> {dest_filename}...")
        subprocess.run(["cp", "-p", src, dest], check=True)

    print("Patching InstallInfo.plist catalog mappings...")
    plist_path = os.path.join(shared_support, "InstallInfo.plist")
    with open(plist_path, "rb") as fp:
        p_data = plistlib.load(fp)

    if "Payload Image Info" in p_data:
        pii = p_data["Payload Image Info"]
        if "URL" in pii:
            pii["URL"] = pii["URL"].replace("InstallESDDmg.pkg", "InstallESD.dmg")
        if "id" in pii:
            pii["id"] = pii["id"].replace("com.apple.pkg.InstallESDDmg", "com.apple.dmg.InstallESD")
        pii.pop("chunklistURL", None)
        pii.pop("chunklistid", None)

    with open(plist_path, "wb") as fp:
        plistlib.dump(p_data, fp)

    print("\033[92m✓ SharedSupport bundle assembled and patched.\033[0m")


def apply_codesign_amfi_fix(dest_app: str):
    print("\n\033[96m=== Step 3: Applying Rosetta / AMFI Code Signature Fix ===\033[0m")
    create_media_binary = os.path.join(
        dest_app, "Contents", "Resources", "createinstallmedia"
    )

    if not os.path.exists(create_media_binary):
        print(f"\033[91m[ERROR] createinstallmedia not found at {create_media_binary}\033[0m")
        sys.exit(1)

    print("Refreshing code signature with ad-hoc identity (codesign -s - --force)...")
    subprocess.run(["codesign", "-s", "-", "--force", create_media_binary], check=True)
    print("\033[92m✓ createinstallmedia is now approved by macOS AMFI for Rosetta 2 execution.\033[0m")
    return create_media_binary


def burn_bootable_usb(create_media_binary: str, target_volume: str):
    print("\n\033[96m=== Step 4: Writing Bootable Media via createinstallmedia ===\033[0m")
    if not os.path.exists(target_volume):
        print(f"\033[91m[ERROR] Target volume '{target_volume}' not found.\033[0m")
        print("Please insert your USB drive and ensure it is mounted.")
        sys.exit(1)

    print(f"Target volume: {target_volume}")
    print("Initiating Apple's official createinstallmedia process...")
    cmd = [create_media_binary, "--volume", target_volume, "--nointeraction"]
    print(f"Executing: {' '.join(cmd)}\n")

    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\n\033[92m" + "=" * 64)
        print("🎉 SUCCESS! Your Bootable macOS USB Installer is ready!")
        print("=" * 64 + "\033[0m")
        print("\nNext steps on your vintage Mac:")
        print("1. Safely eject the USB drive and plug it into your vintage Mac.")
        print("2. Hold down the Option (Alt) key while powering on the Mac.")
        print("3. Select the 'Install macOS' drive and proceed to installation.\n")
    else:
        print(f"\n\033[91m[ERROR] createinstallmedia exited with code {res.returncode}\033[0m")
        sys.exit(res.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Create bootable legacy macOS USB installers on modern Apple Silicon Macs."
    )
    parser.add_argument(
        "--volume",
        default=DEFAULT_TARGET_VOLUME,
        help=f"Path to mounted target USB volume (default: {DEFAULT_TARGET_VOLUME})"
    )
    parser.add_argument(
        "--source-dir",
        default=DEFAULT_SOURCE_DIR,
        help=f"Path to downloaded package chunks directory (default: {DEFAULT_SOURCE_DIR})"
    )
    parser.add_argument(
        "--dest-app",
        default=DEFAULT_DEST_APP,
        help=f"Destination path for assembled installer app (default: {DEFAULT_DEST_APP})"
    )

    args = parser.parse_args()
    check_root()

    # Check if target volume exists or fallback to OS X Base System
    target_vol = args.volume
    if not os.path.exists(target_vol) and os.path.exists("/Volumes/OS X Base System"):
        target_vol = "/Volumes/OS X Base System"

    # Check if app is already assembled
    shared_support = os.path.join(args.dest_app, "Contents", "SharedSupport")
    esd_file = os.path.join(shared_support, "InstallESD.dmg")

    if not os.path.exists(esd_file):
        print(f"\033[1mChecking source files in: {args.source_dir}\033[0m")
        if not os.path.exists(args.source_dir):
            print(f"\033[91m[ERROR] Source directory '{args.source_dir}' does not exist.\033[0m")
            print("Please download the High Sierra packages using mist-cli or gibMacOS first.")
            sys.exit(1)

        for filename in REQUIRED_FILES:
            filepath = os.path.join(args.source_dir, filename)
            if not os.path.exists(filepath):
                print(f"\033[91m[ERROR] Missing required file: {filepath}\033[0m")
                sys.exit(1)

        extract_installer_app(args.source_dir, args.dest_app)
        assemble_shared_support(args.source_dir, args.dest_app)
    else:
        print(f"\033[92m✓ Detected existing assembled installer: {args.dest_app}\033[0m")

    create_media = apply_codesign_amfi_fix(args.dest_app)
    burn_bootable_usb(create_media, target_vol)


if __name__ == "__main__":
    main()
