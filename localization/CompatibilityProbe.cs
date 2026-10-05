// Read-only local compatibility analysis; writes reports only to stdout.
using System;
using System.IO;
using System.Reflection;
using System.Collections;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

static class CompatibilityProbe
{
    const BindingFlags Methods = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static;
    static int Main(string[] args)
    {
        try
        {
            if (args.Length < 2 || args.Length > 3) throw new ArgumentException("Usage: CompatibilityProbe engine.exe game-root [alternate-payload.dat]");
            Assembly assembly = Assembly.LoadFrom(Path.GetFullPath(args[0]));
            Type type = assembly.GetType("Aion2CNTool.CompatibilityEngine", true);
            object engine = type.GetMethod("Load", Methods).Invoke(null, null);
            string pak = Path.Combine(args[1], @"Aion2\Content\Paks\L10N\Text\en-US\pakchunk502000-Windows_0_P.pak");
            byte[] current = (byte[])type.GetMethod("ReadPak", Methods).Invoke(engine, new object[] {pak, args[1]});
            byte[] payload;
            using (Stream input = assembly.GetManifestResourceStream("Aion2CNTool.Payload.L10NString.dat"))
            using (var output = new MemoryStream()) { input.CopyTo(output); payload = output.ToArray(); }
            object source = type.GetMethod("Decode", Methods).Invoke(engine, new object[] {current});
            object translated = type.GetMethod("Decode", Methods).Invoke(engine, new object[] {payload});
            if (args.Length == 3)
                translated = type.GetMethod("Decode", Methods).Invoke(engine, new object[] {File.ReadAllBytes(args[2])});
            object result = type.GetMethod("Merge", Methods).Invoke(engine, new object[] {source, translated});
            var report = new System.Collections.Generic.Dictionary<string, object>();
            foreach (FieldInfo field in result.GetType().GetFields(Methods))
                if (field.FieldType == typeof(int)) report[field.Name] = field.GetValue(result);
            var sourceRows = (IEnumerable)source.GetType().GetField("Rows", Methods).GetValue(source);
            var translatedRows = (IEnumerable)translated.GetType().GetField("Rows", Methods).GetValue(translated);
            var translatedKeys = new System.Collections.Generic.HashSet<string>(StringComparer.Ordinal);
            foreach (object row in translatedRows)
                translatedKeys.Add((string)row.GetType().GetField("Key", Methods).GetValue(row));
            int absent = 0;
            foreach (object row in sourceRows)
                if (!translatedKeys.Contains((string)row.GetType().GetField("Key", Methods).GetValue(row))) absent++;
            report["MissingTranslationKeys"] = absent;
            // New/renamed keys may have an English value already translated
            // elsewhere. Compare the full source fingerprint, never key names.
            var references = (Dictionary<string, byte[]>)type.GetField("Sources", Methods).GetValue(engine);
            var bySource = new Dictionary<string, string>(StringComparer.Ordinal);
            var ambiguous = new HashSet<string>(StringComparer.Ordinal);
            foreach (object row in translatedRows)
            {
                string key = (string)row.GetType().GetField("Key", Methods).GetValue(row);
                string value = (string)row.GetType().GetField("Value", Methods).GetValue(row);
                byte[] fingerprint;
                if (!references.TryGetValue(key, out fingerprint)) continue;
                string digest = BitConverter.ToString(fingerprint);
                string previous;
                if (bySource.TryGetValue(digest, out previous) && previous != value) ambiguous.Add(digest);
                else bySource[digest] = value;
            }
            int equivalentAdded = 0, equivalentChanged = 0;
            using (var hash = SHA256.Create())
            foreach (object row in sourceRows)
            {
                string key = (string)row.GetType().GetField("Key", Methods).GetValue(row);
                string value = (string)row.GetType().GetField("Value", Methods).GetValue(row);
                string digest = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(value)));
                byte[] original;
                bool added = !references.TryGetValue(key, out original);
                if (!added && BitConverter.ToString(original) == digest) continue;
                string replacement;
                if (ambiguous.Contains(digest) || !bySource.TryGetValue(digest, out replacement)) continue;
                var tokens = type.GetMethod("SafeTokens", Methods);
                if (!(bool)tokens.Invoke(null, new object[] {value, replacement})) continue;
                if (added) equivalentAdded++; else equivalentChanged++;
            }
            report["EquivalentSourceAdded"] = equivalentAdded;
            report["EquivalentSourceChanged"] = equivalentChanged;
            int supplemented;
            byte[] supplementedPayload = EquivalentTranslations.Merge(engine, source, translated, out supplemented, false);
            report["SupplementedTranslations"] = supplemented;
            report["SupplementedPayloadBytes"] = supplementedPayload.Length;
            object finalTable = type.GetMethod("Decode", Methods).Invoke(engine, new object[] {supplementedPayload});
            var sourceIterator = sourceRows.GetEnumerator();
            int finalRows = 0, remainingAdded = 0, remainingChanged = 0;
            var unresolved = new List<string>();
            foreach (object row in (IEnumerable)finalTable.GetType().GetField("Rows", Methods).GetValue(finalTable))
            {
                if (!sourceIterator.MoveNext()) throw new InvalidDataException("Final table has extra rows.");
                string key = (string)row.GetType().GetField("Key", Methods).GetValue(row);
                string value = (string)row.GetType().GetField("Value", Methods).GetValue(row);
                string originalKey = (string)sourceIterator.Current.GetType().GetField("Key", Methods).GetValue(sourceIterator.Current);
                string originalValue = (string)sourceIterator.Current.GetType().GetField("Value", Methods).GetValue(sourceIterator.Current);
                if (key != originalKey) throw new InvalidDataException("Final key order changed.");
                finalRows++;
                if (value != originalValue || !Regex.IsMatch(value, @"[A-Za-z]{3}")) continue;
                byte[] reference;
                bool added = !references.TryGetValue(key, out reference);
                using (var digest = SHA256.Create())
                    if (!added && BitConverter.ToString(reference) == BitConverter.ToString(digest.ComputeHash(Encoding.UTF8.GetBytes(originalValue)))) continue;
                if (added) remainingAdded++; else remainingChanged++;
                unresolved.Add(key);
            }
            if (sourceIterator.MoveNext()) throw new InvalidDataException("Final table is missing rows.");
            report["FinalKeyCount"] = finalRows;
            report["RemainingAddedEnglishCandidates"] = remainingAdded;
            report["RemainingChangedEnglishCandidates"] = remainingChanged;
            report["RemainingEnglishCandidateKeys"] = unresolved;
            Console.WriteLine(new JavaScriptSerializer().Serialize(report));
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
