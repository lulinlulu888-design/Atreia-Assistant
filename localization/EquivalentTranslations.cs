// Extends the version-pinned codec without changing or copying its implementation.
// A new key is translated only when its full source matches an unambiguous
// reference source and its formatting tokens are preserved.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

static class EquivalentTranslations
{
    const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
    internal static byte[] Merge(object codec, object current, object translated, out int supplemented, bool requireCoverage = true)
    {
        Type type = codec.GetType();
        object result = type.GetMethod("Merge", Flags).Invoke(codec, new object[] {current, translated});
        byte[] basePayload = (byte[])result.GetType().GetField("Payload", Flags).GetValue(result);
        object output = type.GetMethod("Decode", Flags).Invoke(codec, new object[] {basePayload});
        var references = (Dictionary<string, byte[]>)type.GetField("Sources", Flags).GetValue(codec);
        var candidates = new Dictionary<string, string>(StringComparer.Ordinal);
        var ambiguous = new HashSet<string>(StringComparer.Ordinal);
        foreach (object row in Rows(translated))
        {
            byte[] original;
            if (!references.TryGetValue(Get(row, "Key"), out original)) continue;
            string digest = BitConverter.ToString(original), value = Get(row, "Value"), previous;
            if (candidates.TryGetValue(digest, out previous) && previous != value) ambiguous.Add(digest);
            else candidates[digest] = value;
        }
        supplemented = 0;
        var originals = Rows(current).GetEnumerator();
        using (var hash = SHA256.Create())
        foreach (object row in Rows(output))
        {
            if (!originals.MoveNext() || Get(originals.Current, "Key") != Get(row, "Key"))
                throw new InvalidOperationException("Merged table key order changed.");
            string source = Get(originals.Current, "Value");
            string digest = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(source)));
            byte[] original;
            if (references.TryGetValue(Get(row, "Key"), out original) && BitConverter.ToString(original) == digest) continue;
            string replacement;
            if (ambiguous.Contains(digest) || !candidates.TryGetValue(digest, out replacement)) continue;
            if (!(bool)type.GetMethod("SafeTokens", Flags).Invoke(null, new object[] {source, replacement})) continue;
            if (replacement == source) continue;
            row.GetType().GetField("Value", Flags).SetValue(row, replacement);
            supplemented++;
        }
        supplemented += OfficialTranslations.Apply(current, output);
        if (requireCoverage) VerifyCoverage(current, output, references);
        byte[] payload = (byte[])type.GetMethod("Encode", Flags).Invoke(codec, new object[] {output});
        object checkedTable = type.GetMethod("Decode", Flags).Invoke(codec, new object[] {payload});
        var expected = Rows(output).GetEnumerator();
        foreach (object row in Rows(checkedTable))
            if (!expected.MoveNext() || Get(expected.Current, "Key") != Get(row, "Key") || Get(expected.Current, "Value") != Get(row, "Value"))
                throw new InvalidOperationException("Supplemented table roundtrip failed.");
        if (expected.MoveNext()) throw new InvalidOperationException("Supplemented table was truncated.");
        return payload;
    }
    static IEnumerable Rows(object table) { return (IEnumerable)table.GetType().GetField("Rows", Flags).GetValue(table); }
    static string Get(object row, string field) { return (string)row.GetType().GetField(field, Flags).GetValue(row); }
    static void VerifyCoverage(object current, object output, Dictionary<string, byte[]> references)
    {
        var originals = Rows(current).GetEnumerator();
        var missing = new List<string>();
        using (var hash = SHA256.Create())
        foreach (object row in Rows(output))
        {
            originals.MoveNext();
            string key = Get(row, "Key"), source = Get(originals.Current, "Value");
            if (Get(row, "Value") != source) continue;
            byte[] reference;
            if (references.TryGetValue(key, out reference) && BitConverter.ToString(reference) == BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(source)))) continue;
            // Image identifiers, runtime variables and the official upscaler
            // brand are not English dialogue and must not be translated.
            if (key == "String_UI_SETTING_TAB_GRAPHIC_SUBTAB_OPTIMIZE_UPSCALER_MOBILE1_body" && source == "Neural Frame Fusion") continue;
            string visible = Regex.Replace(source, @"<[^>]*>|\{[^}]*\}", "");
            if (Regex.IsMatch(visible, @"[A-Za-z]{3}")) missing.Add(key);
        }
        if (missing.Count != 0)
            throw new InvalidDataException("当前客户端仍有 " + missing.Count + " 条新增或变更文本缺少补译，未修改游戏。请使用包含对应版本补译的完整汉化组件。首项：" + missing[0]);
    }
}
