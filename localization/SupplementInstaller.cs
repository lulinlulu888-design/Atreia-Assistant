using System;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;

static class SupplementInstaller
{
    const BindingFlags Flags = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    internal static int Install(object form, Assembly assembly, string root)
    {
        Type type = form.GetType();
        Invoke(form, "EnsureGameClosed");
        string source = (string)Invoke(form, "FindSourcePak");
        if (source == null) throw new InvalidOperationException("找不到当前版本的原始英文语言包，请先检查游戏文件。");
        string sourceHash = Digest(File.ReadAllBytes(source));
        Type codecType = assembly.GetType("Aion2CNTool.CompatibilityEngine", true);
        object codec = codecType.GetMethod("Load", Flags).Invoke(null, null);
        byte[] sourceBytes = (byte[])codecType.GetMethod("ReadPak", Flags).Invoke(codec, new object[] {source, root});
        byte[] translatedBytes;
        using (Stream stream = assembly.GetManifestResourceStream("Aion2CNTool.Payload.L10NString.dat"))
        using (var output = new MemoryStream()) { stream.CopyTo(output); translatedBytes = output.ToArray(); }
        object current = codecType.GetMethod("Decode", Flags).Invoke(codec, new object[] {sourceBytes});
        object translated = codecType.GetMethod("Decode", Flags).Invoke(codec, new object[] {translatedBytes});
        int supplemented;
        byte[] payload = EquivalentTranslations.Merge(codec, current, translated, out supplemented);
        if (Digest(File.ReadAllBytes(source)) != sourceHash) throw new IOException("生成译文期间语言包发生变化，请等待游戏更新完成。");
        type.GetField("installedPayloadHash", Flags).SetValue(form, Digest(payload));
        string build = (string)Invoke(form, "CurrentGameBuild");
        type.GetField("installedGameBuild", Flags).SetValue(form, build ?? "source-sha256-" + sourceHash);
        using (var migration = (IDisposable)Invoke(form, "BeginBackupMigration", source, sourceHash))
        {
            Invoke(form, "EnsureGameClosed");
            string checkedBuild = (string)Invoke(form, "CurrentGameBuild");
            if (checkedBuild != build || Digest(File.ReadAllBytes(source)) != sourceHash)
                throw new IOException("安装前游戏版本发生变化，已取消操作。");
            Invoke(form, "InstallPrepared", payload);
            migration.GetType().GetMethod("Commit", Flags).Invoke(migration, null);
        }
        return supplemented;
    }
    static object Invoke(object instance, string name, params object[] args)
    {
        return instance.GetType().GetMethod(name, Flags).Invoke(instance, args);
    }
    static string Digest(byte[] bytes)
    {
        using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", "");
    }
}
