// Acknowledge only the pinned engine's informational success dialog, never consent.
using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

sealed class LegacyCompletionDialog : IDisposable
{
    delegate IntPtr Hook(int code, IntPtr window, IntPtr data);
    readonly Hook callback;
    readonly object form;
    readonly string root;
    IntPtr handle;
    internal bool Acknowledged { get; private set; }

    internal LegacyCompletionDialog(object form, string root)
    {
        this.form = form;
        this.root = root;
        callback = OnHook;
        handle = SetWindowsHookEx(12, callback, IntPtr.Zero, GetCurrentThreadId());
        if (handle == IntPtr.Zero) throw new InvalidOperationException("无法准备汉化完成通知，未开始安装。");
    }

    [StructLayout(LayoutKind.Sequential)]
    struct ReturnedMessage
    {
        internal IntPtr Result, LParam, WParam;
        internal uint Id;
        internal IntPtr Window;
    }

    IntPtr OnHook(int code, IntPtr wParam, IntPtr data)
    {
        if (code >= 0 && !Acknowledged)
        {
            try
            {
                var returned = (ReturnedMessage)Marshal.PtrToStructure(data, typeof(ReturnedMessage));
                if (returned.Id != 0x0110) return CallNextHookEx(handle, code, wParam, data);
                IntPtr window = returned.Window;
                var title = new StringBuilder(128);
                GetWindowText(window, title, title.Capacity);
                var message = new StringBuilder(512);
                GetDlgItemText(window, 65535, message, message.Capacity);
                uint process;
                uint thread = GetWindowThreadProcessId(window, out process);
                if (thread == GetCurrentThreadId() && process == GetCurrentProcessId() &&
                    MatchesNotification(title.ToString(), message.ToString()) &&
                    HasVerifiedInstalledPayload())
                {
                    Acknowledged = EndDialog(window, new IntPtr(1));
                }
            }
            catch { /* Leave unfamiliar or unverifiable dialogs human-controlled. */ }
        }
        return CallNextHookEx(handle, code, wParam, data);
    }

    internal static bool MatchesNotification(string title, string message)
    {
        return title == "安装完成" && message != null &&
            message.Replace("\r\n", "\n") == "汉化安装完成，可以启动游戏。\n\n如遇到异常，可随时运行本工具并点击“一键还原”。";
    }

    bool HasVerifiedInstalledPayload()
    {
        var field = form.GetType().GetField("installedPayloadHash", BindingFlags.Instance | BindingFlags.NonPublic);
        string expected = field == null ? null : field.GetValue(form) as string;
        if (String.IsNullOrEmpty(expected)) return false;
        string directory = Path.Combine(root, @"Aion2\Content\L10N\Text\en-US");
        string state = File.ReadAllText(Path.Combine(directory, "Aion2CNTool.state"));
        if (Array.IndexOf(state.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries), "status=installed") < 0 ||
            Array.IndexOf(state.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries), "payload_hash=" + expected) < 0) return false;
        using (var hash = SHA256.Create())
        using (var stream = File.OpenRead(Path.Combine(directory, "L10NString.dat")))
            return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "") == expected;
    }

    public void Dispose()
    {
        if (handle != IntPtr.Zero) { UnhookWindowsHookEx(handle); handle = IntPtr.Zero; }
        GC.KeepAlive(callback);
    }

    [DllImport("user32.dll", SetLastError = true)] static extern IntPtr SetWindowsHookEx(int type, Hook callback, IntPtr module, uint thread);
    [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr window, IntPtr data);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr window, StringBuilder text, int size);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern uint GetDlgItemText(IntPtr dialog, int item, StringBuilder text, int size);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll")] static extern bool EndDialog(IntPtr window, IntPtr result);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("kernel32.dll")] static extern uint GetCurrentProcessId();
}
