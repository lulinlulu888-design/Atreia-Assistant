// Reads language resources with the exact member spelling listed by repak.
// PAK member lookup is case-sensitive even on Windows; game files stay read-only.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;

static class LanguagePakReader
{
    const BindingFlags Flags = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    // Matches CompatibilityEngine.MaxBytes in the reviewed v2.4.0 engine.
    const int PayloadLimit = 256 * 1024 * 1024;
    const int ListingLimit = 32 * 1024 * 1024;
    const int ProcessTimeout = 60000;
    const string DecoderName = "oo2core_9_win64.dll";

    internal static string ExpectedMember(string locale)
    {
        if (locale == "manifest") return "Aion2/Content/StartUpData/Table/key_manifest.dat";
        if (locale != "en-US" && locale != "zh-TW" && locale != "ko-KR")
            throw new ArgumentException("不支持此语言资源。");
        return "Aion2/Content/L10N/Text/" + locale + "/L10NString.dat";
    }

    internal static string SelectMember(string listing, string locale)
    {
        string expected = ExpectedMember(locale), selected = null;
        using (var lines = new StringReader(listing))
        {
            string member;
            while ((member = lines.ReadLine()) != null)
            {
                if (!string.Equals(member, expected, StringComparison.OrdinalIgnoreCase)) continue;
                if (selected != null) throw new InvalidDataException("当前语言包存在多个同名资源，已停止处理。");
                selected = member;
            }
        }
        if (selected == null) throw new InvalidDataException("当前语言包中找不到所选语言表，游戏资源格式可能已更新。");
        // Only a complete approved path can reach repak get; never normalize
        // traversal, prefixes, backslashes or unrelated filenames into a match.
        return selected;
    }

    internal static byte[] ExtractMember(string listing, string locale, Func<string, byte[]> extract)
    {
        byte[] payload = extract(SelectMember(listing, locale));
        if (payload == null || payload.Length == 0) throw new InvalidDataException("当前语言资源为空，已停止处理。");
        if (payload.Length > PayloadLimit) throw new InvalidDataException("语言资源超过安全大小限制，已停止处理。");
        return payload;
    }

    internal static byte[] Read(Assembly assembly, object codec, string pak, string locale = "en-US", string decoderPath = null)
    {
        if (locale != "list") ExpectedMember(locale);
        string source = Path.GetFullPath(pak);
        if (!File.Exists(source)) throw new FileNotFoundException("找不到当前版本的原始语言包，请检查游戏文件。");
        string decoder = FindDecoder(assembly, decoderPath);
        byte[] key = (byte[])codec.GetType().GetField("pakKey", Flags).GetValue(codec);
        if (key == null || key.Length != 32) throw new InvalidDataException("汉化引擎的语言包配置不兼容。");
        string stage = Path.Combine(Path.GetTempPath(), "Atreia-pak-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(stage);
        try
        {
            string helper = Path.Combine(stage, "repak.exe");
            using (Stream input = assembly.GetManifestResourceStream("Aion2CNTool.Compatibility.Repak.exe"))
            {
                if (input == null) throw new InvalidDataException("缺少核准的语言解包组件，请重新安装助手。");
                using (var output = new FileStream(helper, FileMode.CreateNew, FileAccess.Write)) input.CopyTo(output);
            }
            File.Copy(decoder, Path.Combine(stage, DecoderName));
            // These arguments are never logged, including on helper failure.
            string prefix = "--aes-key " + BitConverter.ToString(key).Replace("-", "");
            byte[] listing = RunTool(helper, prefix + " list " + Quote(source), stage, ListingLimit, ProcessTimeout);
            if (locale == "list") return listing;
            return ExtractMember(new UTF8Encoding(false, true).GetString(listing), locale,
                member => RunTool(helper, prefix + " get " + Quote(source) + " " + Quote(member), stage, PayloadLimit, ProcessTimeout));
        }
        finally
        {
            // Cleanup must not replace the useful read/format/timeout error.
            try { Directory.Delete(stage, true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    static string FindDecoder(Assembly assembly, string explicitPath)
    {
        var candidates = new List<string>();
        if (explicitPath != null) candidates.Add(Path.GetFullPath(explicitPath));
        else
        {
            foreach (string directory in new[] { AppDomain.CurrentDomain.BaseDirectory, Path.GetDirectoryName(assembly.Location) })
            {
                candidates.Add(Path.Combine(directory, "dependencies", DecoderName));
                candidates.Add(Path.Combine(directory, DecoderName));
            }
        }
        foreach (string candidate in candidates)
        {
            if (!File.Exists(candidate)) continue;
            string digest;
            using (var hash = SHA256.Create()) using (var input = File.OpenRead(candidate))
                digest = BitConverter.ToString(hash.ComputeHash(input)).Replace("-", "");
            if (digest != "6F5D41A7892EA6B2DB420F2458DAD2F84A63901C9A93CE9497337B16C195F457" &&
                digest != "8595A4795F1E0C7F548598F3E2AA528B6BE5456C6D934C665182EAECB04156C0")
                throw new InvalidDataException("语言解码组件与核准版本不一致，请重新安装助手。");
            return candidate;
        }
        throw new FileNotFoundException("缺少核准的语言解码组件，请重新安装助手。");
    }

    static string Quote(string argument)
    {
        if (argument.IndexOfAny(new[] { '"', '\r', '\n', '\0' }) >= 0)
            throw new ArgumentException("语言包资源路径无效，已停止处理。");
        return "\"" + argument + "\"";
    }

    static byte[] ReadBounded(Stream input, int limit)
    {
        using (var output = new MemoryStream())
        {
            var buffer = new byte[65536];
            int read;
            while ((read = input.Read(buffer, 0, buffer.Length)) != 0)
            {
                if (output.Length + read > limit) throw new InvalidDataException("解包输出超过安全大小限制，已停止处理。");
                output.Write(buffer, 0, read);
            }
            return output.ToArray();
        }
    }

    // Kept independently testable with harmless synthetic child processes.
    internal static byte[] RunTool(string helper, string arguments, string directory, int limit, int timeout)
    {
        var start = new ProcessStartInfo(helper, arguments) {
            WorkingDirectory = directory, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true
        };
        using (var process = new Process { StartInfo = start })
        {
            try
            {
                try { process.Start(); }
                catch { throw new IOException("无法启动语言解包组件，请检查助手文件是否完整。"); }
                var watch = Stopwatch.StartNew();
                Task<byte[]> output = Task.Factory.StartNew(() => ReadBounded(process.StandardOutput.BaseStream, limit));
                Task<byte[]> errors = Task.Factory.StartNew(() => ReadBounded(process.StandardError.BaseStream, 65536));
                while (!process.WaitForExit(25))
                {
                    if (output.IsFaulted || errors.IsFaulted) throw new InvalidDataException("解包输出超过安全大小限制，已停止处理。");
                    if (watch.ElapsedMilliseconds >= timeout) throw new TimeoutException("语言解包超时，请稍后重试。");
                }
                int remaining = Math.Max(0, timeout - (int)Math.Min(watch.ElapsedMilliseconds, int.MaxValue));
                try
                {
                    if (!Task.WaitAll(new Task[] { output, errors }, remaining)) throw new TimeoutException("语言解包超时，请稍后重试。");
                }
                catch (AggregateException) { throw new InvalidDataException("无法在安全大小限制内读取语言资源，已停止处理。"); }
                if (process.ExitCode != 0) throw new InvalidDataException("当前语言包无法解包，资源格式可能已更新，已停止处理。");
                return output.Result;
            }
            finally
            {
                try { if (!process.HasExited) { process.Kill(); process.WaitForExit(2000); } }
                catch (InvalidOperationException) { }
            }
        }
    }
}
