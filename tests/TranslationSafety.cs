using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

static class TranslationSafety
{
    public class Row { public string Key; public string Value; }
    public class Table { public List<Row> Rows = new List<Row>(); }
    static Table TableOf(string key, string value) { return new Table { Rows = new List<Row> { new Row { Key = key, Value = value } } }; }
    static object Entry(string source, string translation)
    {
        using (var hash = SHA256.Create()) return new { source_sha256 = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(source))).Replace("-", "").ToLowerInvariant(), translation = translation };
    }
    static void Check(bool result, string message) { if (!result) throw new Exception(message); }
    static bool Fails(Action action)
    {
        try { action(); return false; }
        catch (InvalidDataException) { return true; }
        catch (TargetInvocationException error) { if (error.InnerException is InvalidDataException) return true; throw; }
    }
    static void Coverage(Table source, Table output)
    {
        typeof(EquivalentTranslations).GetMethod("VerifyCoverage", BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, new object[] {source, output, new Dictionary<string, byte[]>()});
    }
    static int Main(string[] args)
    {
        try
        {
            if (args.Length == 1)
            {
                var entries = new Dictionary<string, object> {
                    { "test.key", new object[] {Entry("Hello {pcname}", "你好，{pcname}"), Entry("Welcome {pcname}", "欢迎，{pcname}")} },
                    { "bad.key", new object[] {Entry("Hello {pcname}", "你好")} },
                    { "conflict.key", new object[] {Entry("Hello", "你好"), Entry("Hello", "欢迎")} }
                };
                byte[] json = Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(new {format = 2, entries = entries}));
                using (var file = new FileStream(args[0], FileMode.CreateNew))
                using (var gzip = new GZipStream(file, CompressionMode.Compress)) gzip.Write(json, 0, json.Length);
                return 0;
            }
            Table hello = TableOf("test.key", "Hello {pcname}"), output = TableOf("test.key", "Hello {pcname}");
            Check(OfficialTranslations.Apply(hello, output) == 1 && output.Rows[0].Value == "你好，{pcname}", "First variant failed");
            Table welcome = TableOf("test.key", "Welcome {pcname}"); output = TableOf("test.key", "Welcome {pcname}");
            Check(OfficialTranslations.Apply(welcome, output) == 1 && output.Rows[0].Value == "欢迎，{pcname}", "Second variant failed");
            output = TableOf("test.key", "已有优质译文{pcname}");
            Check(OfficialTranslations.Apply(hello, output) == 0 && output.Rows[0].Value == "已有优质译文{pcname}", "Reviewed translation overwritten");
            Table changed = TableOf("test.key", "Changed {pcname}"); output = TableOf("test.key", "Changed {pcname}");
            Check(OfficialTranslations.Apply(changed, output) == 0, "Wrong source digest was accepted");
            Check(Fails(() => OfficialTranslations.Apply(TableOf("bad.key", "Hello {pcname}"), TableOf("bad.key", "Hello {pcname}"))), "Parameter loss accepted");
            Check(Fails(() => OfficialTranslations.Apply(TableOf("conflict.key", "Hello"), TableOf("conflict.key", "Hello"))), "Conflicting variants accepted");
            Check(Fails(() => OfficialTranslations.Apply(hello, TableOf("other.key", "Hello {pcname}"))), "Key mutation accepted");
            Check(Fails(() => Coverage(changed, TableOf("test.key", "Changed {pcname}"))), "Missing translation passed installation gate");
            Coverage(hello, TableOf("test.key", "你好，{pcname}"));
            Table icon = TableOf("icon", "<img id=\"EnglishIdentifier\"/>"); Coverage(icon, icon);
            Table brand = TableOf("String_UI_SETTING_TAB_GRAPHIC_SUBTAB_OPTIMIZE_UPSCALER_MOBILE1_body", "Neural Frame Fusion"); Coverage(brand, brand);
            Console.WriteLine("PASS: 11 translation safety checks (source binding, variants, parameters, conflicts, key order, coverage)");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
