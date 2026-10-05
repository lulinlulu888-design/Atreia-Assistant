using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

// Local official text is embedded at build time, never downloaded during install.
// Each replacement is bound to the exact English source, not merely its key.
static class OfficialTranslations
{
    const BindingFlags Flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    static readonly Regex Parameters = new Regex(@"\{[^}]*\}|%\d*\$?[a-zA-Z](?![a-zA-Z])|\\[nrt]");
    internal static int Apply(object current, object output)
    {
        using (Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("Atreia.Localization.OfficialAdditions.gz"))
        {
            if (resource == null) return 0;
            string json;
            using (var unzip = new GZipStream(resource, CompressionMode.Decompress))
            using (var buffer = new MemoryStream())
            {
                byte[] chunk = new byte[65536]; int read;
                while ((read = unzip.Read(chunk, 0, chunk.Length)) != 0)
                {
                    if (buffer.Length + read > 128 * 1024 * 1024) throw new InvalidDataException("Official additions exceed size limit.");
                    buffer.Write(chunk, 0, read);
                }
                json = new UTF8Encoding(false, true).GetString(buffer.ToArray());
            }
            var serializer = new JavaScriptSerializer { MaxJsonLength = 128 * 1024 * 1024 };
            var document = serializer.Deserialize<Dictionary<string, object>>(json);
            int format = Convert.ToInt32(document["format"]);
            if (format != 1 && format != 2) throw new InvalidDataException("Unsupported official additions format.");
            var entries = (Dictionary<string, object>)document["entries"];
            var originals = ((IEnumerable)current.GetType().GetField("Rows", Flags).GetValue(current)).GetEnumerator();
            int applied = 0;
            using (var hash = SHA256.Create())
            foreach (object row in (IEnumerable)output.GetType().GetField("Rows", Flags).GetValue(output))
            {
                if (!originals.MoveNext() || Get(originals.Current, "Key") != Get(row, "Key")) throw new InvalidDataException("Official additions key order mismatch.");
                string source = Get(originals.Current, "Value");
                // Keep existing reviewed translations; fill only unresolved source text.
                if (Get(row, "Value") != source) continue;
                object entry;
                if (!entries.TryGetValue(Get(row, "Key"), out entry)) continue;
                string digest = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(source))).Replace("-", "").ToLowerInvariant();
                Dictionary<string, object> item = null;
                IEnumerable variants = format == 1 ? (IEnumerable)new object[] { entry } : (IEnumerable)entry;
                foreach (object variant in variants)
                {
                    var candidate = (Dictionary<string, object>)variant;
                    if ((string)candidate["source_sha256"] != digest) continue;
                    if (item != null && (string)item["translation"] != (string)candidate["translation"])
                        throw new InvalidDataException("Conflicting official translation variants.");
                    item = candidate;
                }
                if (item == null) continue;
                string replacement = (string)item["translation"];
                if (Tokens(source) != Tokens(replacement)) throw new InvalidDataException("Official addition changes runtime parameters: " + Get(row, "Key"));
                if (replacement == source) continue;
                row.GetType().GetField("Value", Flags).SetValue(row, replacement);
                applied++;
            }
            if (originals.MoveNext()) throw new InvalidDataException("Official additions table truncated.");
            return applied;
        }
    }
    static string Get(object row, string field) { return (string)row.GetType().GetField(field, Flags).GetValue(row); }
    static string Tokens(string text)
    {
        var tokens = new List<string>();
        foreach (Match match in Parameters.Matches(text)) tokens.Add(match.Value);
        tokens.Sort(StringComparer.Ordinal);
        return string.Join("\u0001", tokens.ToArray());
    }
}
