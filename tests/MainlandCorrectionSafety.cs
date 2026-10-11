using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

static class MainlandCorrectionSafety
{
    public class Row { public string Key; public string Value; }
    public class Table { public List<Row> Rows = new List<Row>(); }
    static Table One(string key, string value) { return new Table { Rows = new List<Row> { new Row { Key = key, Value = value } } }; }
    static string Digest(string text)
    {
        using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(text))).Replace("-", "").ToLowerInvariant();
    }
    static object Correction(string source, string old, string text)
    {
        return new { source_sha256 = Digest(source), previous_translation_sha256 = Digest(old), translation = text };
    }
    static void Check(bool result, string message) { if (!result) throw new Exception(message); }
    static bool Fails(Action action)
    {
        try { action(); return false; }
        catch (InvalidDataException) { return true; }
    }
    static Dictionary<string, string> Read(string path)
    {
        return new JavaScriptSerializer { MaxJsonLength = 128 * 1024 * 1024 }.Deserialize<Dictionary<string, string>>(File.ReadAllText(path, Encoding.UTF8));
    }
    static int Main(string[] args)
    {
        try
        {
            if (args.Length == 3)
            {
                // Read-only integration check against staged tables; no game writes.
                var source = Read(args[0]); var old = Read(args[1]); var expected = Read(args[2]);
                Check(source.Count == old.Count && old.Count == expected.Count, "Key counts differ");
                var current = new Table(); var output = new Table();
                int expectedChanges = 0;
                foreach (var item in source)
                {
                    current.Rows.Add(new Row { Key = item.Key, Value = item.Value });
                    output.Rows.Add(new Row { Key = item.Key, Value = old[item.Key] });
                    if (old[item.Key] != expected[item.Key]) expectedChanges++;
                }
                int applied = OfficialTranslations.Apply(current, output);
                Check(applied == expectedChanges, "Applied correction count differs");
                foreach (var row in output.Rows) Check(row.Value == expected[row.Key], "Runtime/preview mismatch: " + row.Key);
                Check(OfficialTranslations.Apply(current, output) == 0, "Corrections are not idempotent");
                Console.WriteLine("PASS: " + source.Count + " rows, " + applied + " corrections, exact preview parity and idempotence");
                return 0;
            }
            if (args.Length == 1)
            {
                var entries = new Dictionary<string, object> {
                    { "two-pass", new object[] { new { source_sha256 = Digest("Hello {0}"), translation = "旧译{0}" } } }
                };
                var corrections = new Dictionary<string, object> {
                    { "name", new object[] {Correction("Israphel", "伊斯拉斐尔", "伊斯拉佩尔")} },
                    { "two-pass", new object[] {Correction("Hello {0}", "旧译{0}", "新译{0}")} },
                    { "bad-parameter", new object[] {Correction("Hello {0}", "旧译{0}", "丢失参数")} },
                    { "bad-tag", new object[] {Correction("<QK>Hello</>", "<QK>旧译</>", "新译")} },
                    { "no-binding", new object[] {new { source_sha256 = Digest("Hello"), translation = "新译" }} },
                    { "conflict", new object[] {Correction("Hello", "旧译", "新译一"), Correction("Hello", "旧译", "新译二")} }
                };
                byte[] json = Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(new { format = 3, entries = entries, corrections = corrections }));
                using (var file = new FileStream(args[0], FileMode.CreateNew))
                using (var gzip = new GZipStream(file, CompressionMode.Compress)) gzip.Write(json, 0, json.Length);
                return 0;
            }
            var original = One("name", "Israphel"); var outputName = One("name", "伊斯拉斐尔");
            Check(OfficialTranslations.Apply(original, outputName) == 1 && outputName.Rows[0].Value == "伊斯拉佩尔", "Correction not applied");
            Check(OfficialTranslations.Apply(original, outputName) == 0, "Correction reapplied");
            var changed = One("name", "自定义译名");
            Check(OfficialTranslations.Apply(original, changed) == 0 && changed.Rows[0].Value == "自定义译名", "Unreviewed old translation overwritten");
            changed = One("name", "伊斯拉斐尔");
            Check(OfficialTranslations.Apply(One("name", "Different source"), changed) == 0 && changed.Rows[0].Value == "伊斯拉斐尔", "Updated source overwritten");
            var twoPass = One("two-pass", "Hello {0}");
            Check(OfficialTranslations.Apply(One("two-pass", "Hello {0}"), twoPass) == 1 && twoPass.Rows[0].Value == "新译{0}", "Addition then correction failed");
            Check(Fails(() => OfficialTranslations.Apply(One("bad-parameter", "Hello {0}"), One("bad-parameter", "旧译{0}"))), "Parameter loss accepted");
            Check(Fails(() => OfficialTranslations.Apply(One("bad-tag", "<QK>Hello</>"), One("bad-tag", "<QK>旧译</>"))), "Tag loss accepted");
            Check(Fails(() => OfficialTranslations.Apply(One("no-binding", "Hello"), One("no-binding", "旧译"))), "Missing binding accepted");
            Check(Fails(() => OfficialTranslations.Apply(One("conflict", "Hello"), One("conflict", "旧译"))), "Conflicting corrections accepted");
            Console.WriteLine("PASS: 9 mainland correction safety checks");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
