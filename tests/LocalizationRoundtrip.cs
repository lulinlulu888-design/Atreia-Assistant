using System;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Windows.Forms;

static class LocalizationRoundtrip
{
    const BindingFlags Flags = BindingFlags.Instance | BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public;
    static string Hash(string file)
    {
        using (var hash = SHA256.Create()) using (var input = File.OpenRead(file))
            return BitConverter.ToString(hash.ComputeHash(input));
    }
    [STAThread]
    static int Main(string[] args)
    {
        try
        {
            string root = Path.GetFullPath(args[1]);
            if (!File.Exists(Path.Combine(root, "isolated-test.marker"))) throw new Exception("Isolated fixture marker missing");
            string pak = Path.Combine(root, @"Aion2\Content\Paks\L10N\Text\en-US\pakchunk502000-Windows_0_P.pak");
            string dat = Path.Combine(root, @"Aion2\Content\L10N\Text\en-US\L10NString.dat");
            string beforePak = Hash(pak), beforeDat = File.Exists(dat) ? Hash(dat) : null;
            Assembly engine = Assembly.LoadFrom(Path.GetFullPath(args[0]));
            Type type = engine.GetType("Aion2CNTool.MainForm", true);
            using (var form = (Form)Activator.CreateInstance(type, true))
            {
                type.GetField("testMode", Flags).SetValue(form, true);
                ((TextBox)type.GetField("steam", Flags).GetValue(form)).Text = root;
                int supplemented = SupplementInstaller.Install(form, engine, root);
                string installedDat = Hash(dat), installedPak = Hash(pak);
                if (Hash(pak + ".aion2cn.v2.backup") != beforePak) throw new Exception("Original backup mismatch");
                if (!File.ReadAllText(pak).StartsWith("AION2CN ")) throw new Exception("Installation marker missing");
                type.GetField("failAfterPayloadForTest", Flags).SetValue(form, true);
                bool failed = false;
                try { SupplementInstaller.Install(form, engine, root); }
                catch (TargetInvocationException) { failed = true; }
                finally { type.GetField("failAfterPayloadForTest", Flags).SetValue(form, false); }
                if (!failed || Hash(dat) != installedDat || Hash(pak) != installedPak) throw new Exception("Interrupted install did not roll back");
                SupplementInstaller.Install(form, engine, root);
                if (Hash(dat) != installedDat) throw new Exception("Repeated install changed payload");
                type.GetMethod("Restore", Flags).Invoke(form, null);
                if (Hash(pak) != beforePak || (beforeDat == null ? File.Exists(dat) : Hash(dat) != beforeDat)) throw new Exception("Restoration mismatch");
                if (args.Length == 3)
                {
                    File.Copy(args[2], pak, true);
                    string updatedHash = Hash(pak);
                    SupplementInstaller.Install(form, engine, root);
                    if (Hash(pak + ".aion2cn.v2.backup") != updatedHash) throw new Exception("Updated game was not backed up");
                    type.GetMethod("Restore", Flags).Invoke(form, null);
                    if (Hash(pak) != updatedHash) throw new Exception("Restore overwrote updated game with an old backup");
                    if (Directory.GetDirectories(Path.GetDirectoryName(pak), "cn-history-*").Length == 0) throw new Exception("Previous backup generation was not preserved");
                }
                Console.WriteLine("PASS " + Path.GetFileName(root) + ": install, repeat install, interrupted update rollback, byte-exact restore; supplemented=" + supplemented);
            }
            return 0;
        }
        catch (Exception error)
        {
            while (error is TargetInvocationException && error.InnerException != null) error = error.InnerException;
            Console.Error.WriteLine(error.Message); return 1;
        }
    }
}
