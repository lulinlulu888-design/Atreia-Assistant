// Build-time staging of resources from the explicitly selected local engine.
using System;
using System.IO;
using System.Reflection;

static class ResourceStage
{
    static int Main(string[] args)
    {
        if (args.Length != 2 || Directory.Exists(args[1])) return 1;
        Assembly engine = Assembly.LoadFrom(Path.GetFullPath(args[0]));
        Directory.CreateDirectory(args[1]);
        foreach (string name in engine.GetManifestResourceNames())
        {
            using (Stream input = engine.GetManifestResourceStream(name))
            using (Stream output = File.Create(Path.Combine(args[1], name))) input.CopyTo(output);
        }
        Console.WriteLine("Staged local engine resources for isolated testing.");
        return 0;
    }
}
