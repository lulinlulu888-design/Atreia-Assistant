// Local maintainer tool. Extracts one user-owned language table into a new
// scratch directory; never modifies the game or prints encryption keys.
using System;
using System.IO;
using System.Reflection;
using System.Diagnostics;
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
            using (var input = File.OpenRead(args[3]))
                if (BitConverter.ToString(hash.ComputeHash(input)).Replace("-", "") != "6F5D41A7892EA6B2DB420F2458DAD2F84A63901C9A93CE9497337B16C195F457")
                    throw new InvalidDataException("Decoder hash mismatch");
            Assembly assembly = Assembly.LoadFrom(Path.GetFullPath(args[0]));
            Type type = assembly.GetType("Aion2CNTool.CompatibilityEngine", true);
            object engine = type.GetMethod("Load", Flags).Invoke(null, null);
            byte[] key = (byte[])type.GetField("pakKey", Flags).GetValue(engine);
            Directory.CreateDirectory(destination);
            string helper = Path.Combine(destination, "repak.exe");
            using (Stream input = assembly.GetManifestResourceStream("Aion2CNTool.Compatibility.Repak.exe"))
            using (Stream output = File.Create(helper)) input.CopyTo(output);
            File.Copy(args[3], Path.Combine(destination, "oo2core_9_win64.dll"));
            string member = args[2] == "manifest" ? "Aion2/Content/StartUpData/Table/key_manifest.dat" : "AION2/Content/L10N/Text/" + args[2] + "/L10NString.dat";
            string operation = args[2] == "list" ? " list \"" + Path.GetFullPath(args[1]) + "\"" : " get \"" + Path.GetFullPath(args[1]) + "\" \"" + member + "\"";
            var start = new ProcessStartInfo(helper, "--aes-key " + BitConverter.ToString(key).Replace("-", "") + operation);
            start.WorkingDirectory = destination;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            string dat = Path.Combine(destination, "L10NString.dat");
            using (var process = Process.Start(start))
            {
                var errors = process.StandardError.ReadToEndAsync();
                using (var output = File.Create(dat)) process.StandardOutput.BaseStream.CopyTo(output);
                process.WaitForExit();
                if (process.ExitCode != 0) throw new InvalidDataException("PAK extraction failed");
            }
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
