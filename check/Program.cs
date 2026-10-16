using System; using DocumentFormat.OpenXml.Packaging; using DocumentFormat.OpenXml.Validation; using DocumentFormat.OpenXml;
foreach (var f in System.IO.Directory.GetFiles(args[0])) {
  if (!(f.EndsWith(".docx") || f.EndsWith(".xlsx"))) continue;
  try {
    OpenXmlPackage doc = f.EndsWith(".docx") ? WordprocessingDocument.Open(f, false) : SpreadsheetDocument.Open(f, false);
    using (doc) {
      var v = new OpenXmlValidator(FileFormatVersions.Office2010);
      int n = 0; var sb = new System.Text.StringBuilder();
      foreach (var e in v.Validate(doc)) { if (n++ < 6) sb.AppendLine($"    {e.Description} | {e.Path?.XPath} | {e.Part?.Uri}"); }
      Console.WriteLine((n == 0 ? "OK  " : "LOI ") + System.IO.Path.GetFileName(f) + " so loi: " + n); Console.Write(sb);
    }
  } catch (Exception ex) { Console.WriteLine("KHONG MO DUOC " + System.IO.Path.GetFileName(f) + ": " + ex.Message); }
}
