using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;

// No game resources or engine binaries are needed for these regressions.
static class LanguagePakReaderSafety
{
    static int checks;
    static void Check(bool result, string message)
    {
        checks++;
        if (!result) throw new Exception(message);
    }

    static bool Fails<T>(Action action) where T : Exception
    {
        try { action(); return false; }
        catch (T) { return true; }
    }

    static int Main(string[] args)
    {
        if (args.Length == 1)
        {
            if (args[0] == "fixture-hang") { Thread.Sleep(5000); return 0; }
            if (args[0] == "fixture-failure") { Console.Error.WriteLine("private-key-do-not-display"); return 7; }
            if (args[0] == "fixture-binary")
            {
                using (var output = Console.OpenStandardOutput())
                {
                    var bytes = new byte[131072];
                    for (int i = 0; i < bytes.Length; i++) bytes[i] = (byte)i;
                    output.Write(bytes, 0, bytes.Length);
                }
                return 0;
            }
            if (args[0] == "fixture-both")
            {
                Console.Error.Write(new string('x', 32000));
                Console.Write("both streams drained");
                return 0;
            }
            return 8;
        }
        try
        {
            const string current = "Aion2/Content/L10N/Text/en-US/L10NString.dat";
            const string old = "AION2/Content/L10N/Text/en-US/L10NString.dat";
            foreach (string exact in new[] { current, old, "aion2/content/l10n/text/EN-us/l10nstring.DAT" })
            {
                string requested = null;
                byte[] result = LanguagePakReader.ExtractMember("unrelated/file.dat\r\n" + exact + "\r\n", "en-US", member => {
                    requested = member;
                    if (member != exact) throw new Exception("Case-sensitive helper lookup failed");
                    return new byte[] { 0, 255, 42 };
                });
                Check(requested == exact && result.Length == 3 && result[1] == 255,
                    "Exact listed member spelling and payload must be retained");
            }
            bool called = false;
            Check(Fails<InvalidDataException>(() => LanguagePakReader.ExtractMember(current + "\n" + old, "en-US", member => {
                called = true; return new byte[] { 1 };
            })) && !called, "Ambiguous case variants must fail before extraction");
            Check(Fails<InvalidDataException>(() => LanguagePakReader.SelectMember(current + "\n" + current, "en-US")),
                "Duplicate exact members must fail");
            Check(Fails<InvalidDataException>(() => LanguagePakReader.ExtractMember("another/table.dat", "en-US", member => {
                called = true; return new byte[] { 1 };
            })) && !called, "Missing member must fail before extraction");
            foreach (string unexpected in new[] {
                "../" + current, "/" + current, current.Replace('/', '\\'),
                "Aion2/Content/L10N/Text/en-US/../en-US/L10NString.dat", current + ".backup"
            }) Check(Fails<InvalidDataException>(() => LanguagePakReader.SelectMember(unexpected, "en-US")),
                "Unexpected path must not become an approved language member");
            Check(Fails<ArgumentException>(() => LanguagePakReader.SelectMember(current, "en-US/../../other")),
                "Unapproved locale must fail");
            const string traditional = "AION2/Content/L10N/Text/zh-TW/L10NString.dat";
            const string korean = "Aion2/Content/L10N/Text/ko-KR/L10NString.dat";
            const string manifest = "AION2/Content/StartUpData/Table/key_manifest.dat";
            Check(LanguagePakReader.SelectMember(traditional, "zh-TW") == traditional, "Traditional locale path failed");
            Check(LanguagePakReader.SelectMember(korean, "ko-KR") == korean, "Korean locale path failed");
            Check(LanguagePakReader.SelectMember(manifest, "manifest") == manifest, "Manifest path failed");
            Check(Fails<InvalidDataException>(() => LanguagePakReader.ExtractMember(current, "en-US", member => new byte[0])),
                "Empty payload must fail");
            CultureInfo previous = Thread.CurrentThread.CurrentCulture;
            try
            {
                Thread.CurrentThread.CurrentCulture = new CultureInfo("tr-TR");
                Check(LanguagePakReader.SelectMember(old, "en-US") == old, "Path selection must be culture independent");
            }
            finally { Thread.CurrentThread.CurrentCulture = previous; }

            string executable = Assembly.GetExecutingAssembly().Location;
            string directory = Path.GetDirectoryName(executable);
            byte[] binary = LanguagePakReader.RunTool(executable, "fixture-binary", directory, 200000, 5000);
            Check(binary.Length == 131072 && binary[0] == 0 && binary[255] == 255,
                "Child-process binary stdout must remain byte exact");
            Check(Fails<InvalidDataException>(() => LanguagePakReader.RunTool(executable, "fixture-binary", directory, 1024, 5000)),
                "Child-process output limit must fail");
            Check(Encoding.UTF8.GetString(LanguagePakReader.RunTool(executable, "fixture-both", directory, 1024, 5000)) == "both streams drained",
                "Both child-process streams must be drained without deadlock");
            var watch = Stopwatch.StartNew();
            Check(Fails<TimeoutException>(() => LanguagePakReader.RunTool(executable, "fixture-hang", directory, 1024, 100)) && watch.ElapsedMilliseconds < 3000,
                "Timed-out child must be terminated promptly");
            bool sanitized = false;
            try { LanguagePakReader.RunTool(executable, "fixture-failure", directory, 1024, 5000); }
            catch (InvalidDataException error) { sanitized = !error.ToString().Contains("private-key-do-not-display"); }
            Check(sanitized, "Helper stderr must not expose sensitive arguments or output");
            Console.WriteLine("PASS: " + checks + " language PAK reader checks (case, uniqueness, approved paths, binary output, limits, timeout)");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
