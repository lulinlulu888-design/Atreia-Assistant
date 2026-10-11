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
    static readonly Regex Tags = new Regex(@"<[^>]*>");
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
            if (format != 1 && format != 2 && format != 3) throw new InvalidDataException("Unsupported official additions format.");
            var entries = (Dictionary<string, object>)document["entries"];
            var corrections = format == 3 ? (Dictionary<string, object>)document["corrections"] : new Dictionary<string, object>();
            var originals = ((IEnumerable)current.GetType().GetField("Rows", Flags).GetValue(current)).GetEnumerator();
            int applied = 0;
            using (var hash = SHA256.Create())
            foreach (object row in (IEnumerable)output.GetType().GetField("Rows", Flags).GetValue(output))
            {
                if (!originals.MoveNext() || Get(originals.Current, "Key") != Get(row, "Key")) throw new InvalidDataException("Official additions key order mismatch.");
                string source = Get(originals.Current, "Value");
                string previous = Get(row, "Value"), value = previous;
                object entry;
                string digest = Digest(hash, source);
                // Old formats still fill only unresolved text. Format 3 has a
                // separate, explicit correction pass bound to both text versions.
                if (value == source && entries.TryGetValue(Get(row, "Key"), out entry))
                {
                    IEnumerable variants = format == 1 ? (IEnumerable)new object[] { entry } : (IEnumerable)entry;
                    string replacement = Select(variants, digest, null);
                    if (replacement != null)
                    {
                        if (Tokens(source) != Tokens(replacement)) throw new InvalidDataException("Official addition changes runtime parameters: " + Get(row, "Key"));
                        value = replacement;
                    }
                }
                if (corrections.TryGetValue(Get(row, "Key"), out entry))
                {
                    string replacement = Select((IEnumerable)entry, digest, Digest(hash, value));
                    if (replacement != null)
                    {
                        if (Tokens(source) != Tokens(replacement) || TagSequence(value) != TagSequence(replacement))
                            throw new InvalidDataException("Mainland correction changes parameters or tags: " + Get(row, "Key"));
                        value = replacement;
                    }
                }
                if (value == previous) continue;
                row.GetType().GetField("Value", Flags).SetValue(row, value);
                applied++;
            }
            if (originals.MoveNext()) throw new InvalidDataException("Official additions table truncated.");
            return applied;
        }
    }
    static string Digest(HashAlgorithm hash, string value)
    {
        return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(value))).Replace("-", "").ToLowerInvariant();
    }
    static string Select(IEnumerable variants, string sourceDigest, string previousDigest)
    {
        string selected = null;
        foreach (object variant in variants)
        {
            var candidate = (Dictionary<string, object>)variant;
            if ((string)candidate["source_sha256"] != sourceDigest) continue;
            if (previousDigest != null)
            {
                object expected;
                if (!candidate.TryGetValue("previous_translation_sha256", out expected) || !(expected is string))
                    throw new InvalidDataException("Mainland correction is missing previous translation binding.");
                if ((string)expected != previousDigest) continue;
            }
            string text = (string)candidate["translation"];
            if (selected != null && selected != text) throw new InvalidDataException("Conflicting official translation variants.");
            selected = text;
        }
        return selected;
    }
    static string TagSequence(string text)
    {
        var tags = new List<string>();
        foreach (Match match in Tags.Matches(text)) tags.Add(match.Value);
        return string.Join("\u0001", tags.ToArray());
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
