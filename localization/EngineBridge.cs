// Atreia's interoperability adapter; does not copy or relicense engine code.
using System;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Windows.Forms;
using System.Web.Script.Serialization;

static class EngineBridge
{
    const string EngineHash = "1D01A3AB4C9604296DA6B2265FD0A5A1247D628D31FD4AB02EB8BAC539340E58";
    const BindingFlags PrivateInstance = BindingFlags.NonPublic | BindingFlags.Instance;
    const BindingFlags CodecFlags = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance;

    static string Inspect(object form, Assembly assembly, string root, string client, out int supplemented)
    {
        string source = (string)form.GetType().GetMethod("FindSourcePak", PrivateInstance).Invoke(form, null);
        if (source == null) throw new InvalidDataException("找不到当前版本的原始英文语言包。");
        Type type = assembly.GetType("Aion2CNTool.CompatibilityEngine", true);
        object codec = type.GetMethod("Load", CodecFlags).Invoke(null, null);
        byte[] sourceBytes = (byte[])type.GetMethod("ReadPak", CodecFlags).Invoke(codec, new object[] {source, root});
        byte[] translatedBytes;
        using (Stream stream = assembly.GetManifestResourceStream("Aion2CNTool.Payload.L10NString.dat"))
        using (var buffer = new MemoryStream()) { stream.CopyTo(buffer); translatedBytes = buffer.ToArray(); }
        object current = type.GetMethod("Decode", CodecFlags).Invoke(codec, new object[] {sourceBytes});
        object translated = type.GetMethod("Decode", CodecFlags).Invoke(codec, new object[] {translatedBytes});
        EquivalentTranslations.Merge(codec, current, translated, out supplemented);
        int count = ((System.Collections.ICollection)current.GetType().GetField("Rows", CodecFlags).GetValue(current)).Count;
        return "已验证 " + client + " 当前语言表：" + count + " 个键，额外补译 " + supplemented + " 条，编码回读及缺译检查通过。安装后请将游戏文字语言设置为 English。检测未修改游戏。";
    }

    static string Hash(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "");
    }

    static string State(string root)
    {
        string path = Path.Combine(root, @"Aion2\Content\L10N\Text\en-US\Aion2CNTool.state");
        if (!File.Exists(path)) return "not_installed";
        if (new FileInfo(path).Length > 65536) throw new InvalidDataException("安装状态文件过大");
        foreach (string line in File.ReadAllLines(path))
            if (line.StartsWith("status=", StringComparison.Ordinal)) return line.Substring(7);
        return "unknown";
    }

    [STAThread]
    static int Main(string[] args)
    {
        Console.OutputEncoding = new System.Text.UTF8Encoding(false);
        string operation = args.Length > 1 ? args[1] : "invalid";
        string root = null;
        string client = args.Length == 4 ? args[3] : null;
        try
        {
            if (args.Length != 4 || (args[3] != "steam" && args[3] != "purple") ||
                (operation != "inspect" && operation != "install" && operation != "restore"))
                throw new ArgumentException("仅支持已明确选择的 Steam 或 PURPLE 客户端及检测、安装、还原操作");
            string engine = Path.GetFullPath(args[0]);
            root = Path.GetFullPath(args[2]);
            if (!Directory.Exists(Path.Combine(root, @"Aion2\Content")))
                throw new DirectoryNotFoundException("目标不是可识别的 AION2 游戏目录");
            if (Hash(engine) != EngineHash)
                throw new InvalidDataException("汉化引擎与核准的 v2.4.0 正式版本不一致");
            Assembly assembly = Assembly.LoadFrom(engine);
            Type type = assembly.GetType("Aion2CNTool.MainForm", true);
            string version = (string)type.GetField("ToolVersion", BindingFlags.Static | BindingFlags.NonPublic).GetRawConstantValue();
            if (version != "2.4.0") throw new InvalidDataException("不支持此汉化引擎接口");
            using (var form = (Form)Activator.CreateInstance(type, true))
            {
                // Do not show the legacy main window or trigger its Shown
                // updater. Its own compatibility/completion prompts remain
                // human-controlled, and its transaction checks stay intact.
                ((TextBox)type.GetField("steam", PrivateInstance).GetValue(form)).Text = root;
                int supplemented = 0;
                string inspection = null;
                if (operation == "install") supplemented = SupplementInstaller.Install(form, assembly, root);
                else if (operation == "inspect") inspection = Inspect(form, assembly, root, args[3], out supplemented);
                else type.GetMethod("Restore", PrivateInstance).Invoke(form, null);
                string state = State(root);
                bool cancelled = operation == "install" &&
                    type.GetField("installedPayloadHash", PrivateInstance).GetValue(form) == null;
                if (!cancelled && operation == "install" && state != "installed")
                    throw new InvalidDataException("引擎返回后未检测到完成的安装状态");
                if (operation == "restore" && state != "restored")
                    throw new InvalidDataException("引擎返回后未检测到完成的还原状态");
                Console.WriteLine(new JavaScriptSerializer().Serialize(new {
                    ok = !cancelled, cancelled = cancelled, operation = operation,
                    client = client, game_root = root,
                    engine_version = version, state = state, supplemented = supplemented,
                    message = cancelled ? "已取消兼容汉化安装" : inspection ?? ("客户端：" + args[3] + "；额外补译：" + supplemented + " 条。\n" + ((TextBox)type.GetField("log", PrivateInstance).GetValue(form)).Text.Replace("新增和变化文本保留当前原文", "新增和变化文本已经过补译完整性检查"))
                }));
                return 0;
            }
        }
        catch (Exception error)
        {
            while (error is TargetInvocationException && error.InnerException != null) error = error.InnerException;
            Console.WriteLine(new JavaScriptSerializer().Serialize(new {
                ok = false, cancelled = false, operation = operation,
                client = client, game_root = root, message = error.Message
            }));
            return 1;
        }
    }
}
