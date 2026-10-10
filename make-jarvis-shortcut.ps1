# Creates the Jarvis icon and the shortcuts (Desktop + Start menu). Pin it to the taskbar from there.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$root = $PSScriptRoot
$icoPath = Join-Path $root 'jarvis.ico'
$src = [System.Drawing.Image]::FromFile((Join-Path $root 'frontend\public\pwa-512x512.png'))
$sizes = 16, 32, 48, 64, 128, 256
$pngs = foreach ($s in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap $s, $s
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = 'HighQualityBicubic'
    $g.DrawImage($src, 0, 0, $s, $s); $g.Dispose()
    $ms = New-Object IO.MemoryStream; $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
    , $ms.ToArray()
}
$src.Dispose()
$out = New-Object IO.MemoryStream; $w = New-Object IO.BinaryWriter $out
$w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]$sizes.Count)
$offset = 6 + 16 * $sizes.Count
for ($i = 0; $i -lt $sizes.Count; $i++) {
    $s = $sizes[$i]; $dim = if ($s -ge 256) { 0 } else { $s }
    $w.Write([byte]$dim); $w.Write([byte]$dim); $w.Write([byte]0); $w.Write([byte]0)
    $w.Write([uint16]1); $w.Write([uint16]32); $w.Write([uint32]$pngs[$i].Length); $w.Write([uint32]$offset)
    $offset += $pngs[$i].Length
}
foreach ($p in $pngs) { $w.Write($p) }
$w.Flush(); [IO.File]::WriteAllBytes($icoPath, $out.ToArray())

# Shortcuts need the same AppUserModelID the app sets at runtime, so the pinned icon and the
# running window are ONE taskbar button with the Jarvis icon.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class LnkAumid {
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore {
        void GetCount(out uint c); void GetAt(uint i, out PROPERTYKEY k); void GetValue(ref PROPERTYKEY k, out PROPVARIANT v);
        void SetValue(ref PROPERTYKEY k, ref PROPVARIANT v); void Commit();
    }
    [StructLayout(LayoutKind.Sequential, Pack = 4)] struct PROPERTYKEY { public Guid fmtid; public uint pid; }
    [StructLayout(LayoutKind.Explicit)] struct PROPVARIANT {
        [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public IntPtr p;
    }
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHGetPropertyStoreFromParsingName(string path, IntPtr bc, int flags, ref Guid iid, out IPropertyStore store);
    public static void Set(string lnkPath, string aumid) {
        Guid iid = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");
        IPropertyStore store;
        int hr = SHGetPropertyStoreFromParsingName(lnkPath, IntPtr.Zero, 2 /*GPS_READWRITE*/, ref iid, out store);
        if (hr != 0) throw new COMException("SHGetPropertyStoreFromParsingName", hr);
        PROPERTYKEY key = new PROPERTYKEY { fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid = 5 };
        PROPVARIANT v = new PROPVARIANT { vt = 31 /*VT_LPWSTR*/, p = Marshal.StringToCoTaskMemUni(aumid) };
        store.SetValue(ref key, ref v); store.Commit();
        Marshal.FreeCoTaskMem(v.p);
    }
}
"@

$aumid = 'Sothe.Jarvis'
$wsh = New-Object -ComObject WScript.Shell
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$targets = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
)
foreach ($dir in $targets) {
    $path = Join-Path $dir 'Jarvis.lnk'
    $lnk = $wsh.CreateShortcut($path)
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = '"' + (Join-Path $root 'jarvis_app.pyw') + '"'
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = $icoPath
    $lnk.Description = 'Jarvis'
    $lnk.Save()
    [LnkAumid]::Set($path, $aumid)
    Write-Host "Created $path"
}

# Autostart at logon: same app (replaces the old browser-based startup shortcut).
$startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\Jarvis-Sothe.lnk'
if (Test-Path $startup) {
    $lnk = $wsh.CreateShortcut($startup)
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = '"' + (Join-Path $root 'jarvis_app.pyw') + '"'
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = $icoPath
    $lnk.Save()
    [LnkAumid]::Set($startup, $aumid)
    Write-Host "Updated $startup"
}
