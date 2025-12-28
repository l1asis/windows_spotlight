import argparse
import ctypes
import os
import shutil
from ctypes import wintypes
from typing import Literal


def get_user_sid() -> str | None:
    """Retrieves the current user's SID as a string."""
    # Define constants
    TOKEN_QUERY = 0x0008
    TOKEN_USER = 1

    # Load necessary Windows libraries
    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32

    # Define function prototypes
    # HANDLE GetCurrentProcess()
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []

    # BOOL OpenProcessToken([in] HANDLE ProcessHandle, [in] DWORD DesiredAccess, [out] PHANDLE TokenHandle)
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.OpenProcessToken.restype = wintypes.BOOL

    # BOOL GetTokenInformation([in] HANDLE TokenHandle, [in] TOKEN_INFORMATION_CLASS TokenInformationClass, [out] LPVOID TokenInformation, [in] DWORD TokenInformationLength, [out] PDWORD ReturnLength)
    advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi32.GetTokenInformation.restype = wintypes.BOOL

    # BOOL ConvertSidToStringSidA([in] PSID Sid, [out] LPSTR *StringSid)
    advapi32.ConvertSidToStringSidA.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
    advapi32.ConvertSidToStringSidA.restype = wintypes.BOOL

    # BOOL CloseHandle([in] HANDLE hObject)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    # Get current process token
    process_handle = kernel32.GetCurrentProcess()
    token_handle = wintypes.HANDLE()

    if not advapi32.OpenProcessToken(process_handle, TOKEN_QUERY, ctypes.byref(token_handle)):
        return None

    # Determine required buffer size
    return_length = wintypes.DWORD()
    advapi32.GetTokenInformation(token_handle, TOKEN_USER, None, 0, ctypes.byref(return_length))

    # Fetch the actual token information
    buffer = ctypes.create_string_buffer(return_length.value)
    if advapi32.GetTokenInformation(token_handle, TOKEN_USER, buffer, return_length.value, ctypes.byref(return_length)):
        # The SID is a pointer within the structure; convert it to a string
        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        string_sid = ctypes.c_char_p()
        advapi32.ConvertSidToStringSidA(sid_pointer, ctypes.byref(string_sid))
        if string_sid.value:
            # Close the token handle
            kernel32.CloseHandle(token_handle)
            return string_sid.value.decode()

    # Close the token handle
    kernel32.CloseHandle(token_handle)
    return None


def clean_directory(directory_path: str) -> None:
    """Deletes all files and subdirectories in the specified directory."""
    for entry in os.scandir(directory_path):
        try:
            if entry.is_file() or entry.is_symlink():
                os.unlink(entry.path)
            elif entry.is_dir():
                shutil.rmtree(entry.path)
        except Exception as e:
            print(f"Failed to delete {entry.path}. Reason: {e}")


def dump_windows_spotlight(
    extract_assets: bool = True,
    extract_desktop: bool = True,
    extract_lockscreen: bool = True,
    orientation: Literal["landscape", "portrait", "both"] = "both",
    output_directory: str = ".\\WindowsSpotlightWallpapers",
    clean_output_directory: bool = False,
) -> None:
    """Extracts Windows Spotlight wallpapers to the specified output directory."""
    user_profile_path = os.getenv("USERPROFILE")
    if not user_profile_path:
        user_profile_path = "C:\\Users\\Default"

    desktop_path = f"{user_profile_path}\\AppData\\Roaming\\Microsoft\\Windows\\Themes\\TranscodedWallpaper"
    assets_path = f"{user_profile_path}\\AppData\\Local\\Packages\\Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy\\LocalState\\Assets"
    lockscreen_path = None
    if extract_lockscreen and (user_sid := get_user_sid()):
        lockscreen_path = f"C:\\ProgramData\\Microsoft\\Windows\\SystemData\\{user_sid}\\ReadOnly"
        if os.access(lockscreen_path, os.R_OK):
            lockscreen_path = None

    os.makedirs(output_directory, exist_ok=True)
    if clean_output_directory:
        clean_directory(output_directory)

    if extract_desktop and os.path.exists(desktop_path) and os.path.isfile(desktop_path):
        shutil.copy2(desktop_path, os.path.join(output_directory, "TranscodedWallpaper.jpg"))

    if extract_assets and os.path.exists(assets_path) and os.path.isdir(assets_path):
        for filename in os.listdir(assets_path):
            source_file = os.path.join(assets_path, filename)
            if os.path.isfile(source_file):
                output_file = os.path.join(output_directory, f"{filename}.jpg")
                shutil.copy2(source_file, output_file)

    if extract_lockscreen and lockscreen_path and os.path.exists(lockscreen_path) and os.path.isdir(lockscreen_path):
        for name in os.listdir(lockscreen_path):
            if name.lower().startswith("lockscreen"):
                for filename in os.listdir(os.path.join(lockscreen_path, name)):
                    source_file = os.path.join(lockscreen_path, name, filename)
                    if os.path.isfile(source_file):
                        output_file = os.path.join(output_directory, f"LockScreen_{filename}.jpg")
                        shutil.copy2(source_file, output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="windows_spotlight", description="Extract Windows Spotlight wallpapers.")
    parser.add_argument("-a", "--assets", action="store_true", help="Extract cached wallpapers from Assets folder")
    parser.add_argument("-d", "--desktop", action="store_true", help="Extract current desktop wallpaper")
    parser.add_argument("-l", "--lockscreen", action="store_true", help="Extract current lock screen wallpaper (Requires admin privileges or ownership)")
    parser.add_argument("-r", "--orientation", type=str, default="both", choices=["landscape", "portrait", "both"], help="Filter wallpapers by orientation (Only for Assets wallpapers)")
    parser.add_argument("-o", "--out", type=str, default=".\\WindowsSpotlightWallpapers", help="Destination directory for extracted wallpapers")
    parser.add_argument("-c", "--clean", action="store_true", help="Clean the destination directory before extraction")
    
    args = parser.parse_args()

    if not args.assets and not args.desktop and not args.lockscreen:
        args.assets = True
        args.desktop = True
        args.lockscreen = True

    dump_windows_spotlight(
        extract_assets=args.assets,
        extract_desktop=args.desktop,
        extract_lockscreen=args.lockscreen,
        orientation=args.orientation,
        output_directory=args.out,
        clean_output_directory=args.clean,
    )
