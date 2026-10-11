using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;

// Exercises the installer's actual merge/encode/readback path without installing.
static class LocalizationPayloadCheck
{
    const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
    static int Main(string[] args)
    {
        try
        {
            if (args.Length != 3) throw new ArgumentException("engine.exe original-pak-root new-output-directory");
            if (Directory.Exists(args[2])) throw new IOException("Output directory must be new.");
            Assembly assembly = Assembly.LoadFrom(Path.GetFullPath(args[0]));
            Type type = assembly.GetType("Aion2CNTool.CompatibilityEngine", true);
            object codec = type.GetMethod("Load", Flags).Invoke(null, null);
            string root = Path.GetFullPath(args[1]);
            string pak = Path.Combine(root, @"Aion2\Content\Paks\L10N\Text\en-US\pakchunk502000-Windows_0_P.pak");
            byte[] original = (byte[])type.GetMethod("ReadPak", Flags).Invoke(codec, new object[] { pak, root });
            byte[] translated;
            using (Stream stream = assembly.GetManifestResourceStream("Aion2CNTool.Payload.L10NString.dat"))
            using (var buffer = new MemoryStream()) { stream.CopyTo(buffer); translated = buffer.ToArray(); }
            object source = type.GetMethod("Decode", Flags).Invoke(codec, new object[] { original });
            object baseline = type.GetMethod("Decode", Flags).Invoke(codec, new object[] { translated });
            int supplemented;
            byte[] payload = EquivalentTranslations.Merge(codec, source, baseline, out supplemented);
            object result = type.GetMethod("Decode", Flags).Invoke(codec, new object[] { payload });
            var rows = new Dictionary<string, string>();
            foreach (object row in (IEnumerable)result.GetType().GetField("Rows", Flags).GetValue(result))
                rows.Add((string)row.GetType().GetField("Key", Flags).GetValue(row), (string)row.GetType().GetField("Value", Flags).GetValue(row));
            Directory.CreateDirectory(args[2]);
            File.WriteAllBytes(Path.Combine(args[2], "payload.dat"), payload);
            File.WriteAllText(Path.Combine(args[2], "translation.json"), new JavaScriptSerializer { MaxJsonLength = 128 * 1024 * 1024 }.Serialize(rows), new UTF8Encoding(false));
            Console.WriteLine("PASS: native coverage, encode and readback; " + rows.Count + " rows; " + supplemented + " supplemented/corrected.");
            return 0;
        }
        catch (Exception error)
        {
            while (error is TargetInvocationException && error.InnerException != null) error = error.InnerException;
            Console.Error.WriteLine(error.Message);
            return 1;
        }
    }
}
