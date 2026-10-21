using System;

static class LegacyCompletionSafety
{
    static int Main()
    {
        const string message = "汉化安装完成，可以启动游戏。\n\n如遇到异常，可随时运行本工具并点击“一键还原”。";
        if (!LegacyCompletionDialog.MatchesNotification("安装完成", message)) throw new Exception("Success notification not recognized");
        if (!LegacyCompletionDialog.MatchesNotification("安装完成", message.Replace("\n", "\r\n"))) throw new Exception("CRLF notification not recognized");
        foreach (string title in new[] { "语言表兼容性检测", "操作失败", "更新工具", "安装确认", "", null })
            if (LegacyCompletionDialog.MatchesNotification(title, message)) throw new Exception("Unexpected dialog acknowledged");
        foreach (string text in new[] { "是否安装？", "安装失败", message + " 是否覆盖文件？", "", null })
            if (LegacyCompletionDialog.MatchesNotification("安装完成", text)) throw new Exception("Unexpected content acknowledged");
        Console.WriteLine("PASS: 13 completion notification checks; consent/error dialogs never match.");
        return 0;
    }
}
