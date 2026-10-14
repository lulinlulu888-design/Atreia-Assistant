// Local maintainer tool. Extracts one user-owned language table into a new
// scratch directory; never modifies the game or prints encryption keys.
using System;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;

static class LocaleProbe
{
    const BindingFlags Flags = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    static int Main(string[] args)
    {
        try
        {
            if (args.Length != 5) throw new ArgumentException("engine.exe language.pak locale oodle.dll new-output-directory");
            string destination = Path.GetFullPath(args[4]);
            if (Directory.Exists(destination)) throw new IOException("Output directory must be new.");
            if (args[2] != "zh-TW" && args[2] != "en-US" && args[2] != "ko-KR" && args[2] != "list" && args[2] != "manifest") throw new ArgumentException("Unknown locale");
            using (var hash = SHA256.Create())
            using (var input = File.OpenRead(args[0]))
                if (BitConverter.ToString(hash.ComputeHash(input)).Replace("-", "") != "1D01A3AB4C9604296DA6B2265FD0A5A1247D628D31FD4AB02EB8BAC539340E58")
                    throw new InvalidDataException("Unreviewed localization engine");
            Assembly assembly = Assembly.LoadFrom(Path.GetFullPath(args[0]));
            Type type = assembly.GetType("Aion2CNTool.CompatibilityEngine", true);
            object engine = type.GetMethod("Load", Flags).Invoke(null, null);
            byte[] data = LanguagePakReader.Read(assembly, engine, args[1], args[2], args[3]);
            Directory.CreateDirectory(destination);
            string dat = Path.Combine(destination, "L10NString.dat");
            using (var output = new FileStream(dat, FileMode.CreateNew)) output.Write(data, 0, data.Length);
            Console.WriteLine("Extracted " + new FileInfo(dat).Length + " bytes to " + dat);
            if (args[2] == "list" || args[2] == "manifest") return 0;
            try
            {
                object table = type.GetMethod("Decode", Flags).Invoke(engine, new object[] {File.ReadAllBytes(dat)});
                var rows = (System.Collections.ICollection)table.GetType().GetField("Rows", Flags).GetValue(table);
                Console.WriteLine("Decoded with existing codec: " + rows.Count + " rows");
            }
            catch (TargetInvocationException) { Console.WriteLine("This locale requires its own container codec configuration."); }
            return 0;
        }
        catch (Exception error)
        {
            while (error is TargetInvocationException && error.InnerException != null) error = error.InnerException;
            Console.Error.WriteLine(error.Message); return 1;
        }
    }
}
