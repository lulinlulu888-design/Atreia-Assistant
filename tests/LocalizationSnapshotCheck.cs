// Maintainer fixture: validates a released source snapshot without a game install.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;

static class LocalizationSnapshotCheck
{
    const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
    static int Main(string[] args)
    {
        try
        {
            if (args.Length != 3 || Directory.Exists(args[2]))
                throw new ArgumentException("engine.exe source.json new-output-directory");
            var serializer = new JavaScriptSerializer { MaxJsonLength = 128 * 1024 * 1024 };
            var snapshot = serializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(args[1], Encoding.UTF8));
            Assembly assembly = Assembly.LoadFrom(Path.GetFullPath(args[0]));
            Type type = assembly.GetType("Aion2CNTool.CompatibilityEngine", true);
            object codec = type.GetMethod("Load", Flags).Invoke(null, null);
            byte[] bytes;
            using (Stream stream = assembly.GetManifestResourceStream("Aion2CNTool.Payload.L10NString.dat"))
            using (var buffer = new MemoryStream()) { stream.CopyTo(buffer); bytes = buffer.ToArray(); }
            object baseline = type.GetMethod("Decode", Flags).Invoke(codec, new object[] { bytes });
            object current = type.GetMethod("Decode", Flags).Invoke(codec, new object[] { bytes });
            var rows = (IList)current.GetType().GetField("Rows", Flags).GetValue(current);
            Type rowType = rows[0].GetType();
            rows.Clear();
            foreach (var entry in snapshot)
            {
                object row = Activator.CreateInstance(rowType, true);
                rowType.GetField("Key", Flags).SetValue(row, entry.Key);
                rowType.GetField("Value", Flags).SetValue(row, entry.Value);
                rows.Add(row);
            }
            int supplemented;
            byte[] payload = EquivalentTranslations.Merge(codec, current, baseline, out supplemented);
            object result = type.GetMethod("Decode", Flags).Invoke(codec, new object[] { payload });
            var translated = new Dictionary<string, string>();
            foreach (object row in (IEnumerable)result.GetType().GetField("Rows", Flags).GetValue(result))
                translated.Add((string)rowType.GetField("Key", Flags).GetValue(row), (string)rowType.GetField("Value", Flags).GetValue(row));
            Directory.CreateDirectory(args[2]);
            File.WriteAllBytes(Path.Combine(args[2], "payload.dat"), payload);
            File.WriteAllText(Path.Combine(args[2], "translation.json"), serializer.Serialize(translated), new UTF8Encoding(false));
            Console.WriteLine("PASS: " + translated.Count + " snapshot rows; " + supplemented + " supplemented/corrected.");
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
