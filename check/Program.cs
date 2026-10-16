using System; using DocumentFormat.OpenXml.Packaging; using DocumentFormat.OpenXml.Validation; using DocumentFormat.OpenXml;
foreach (var f in System.IO.Directory.GetFiles(args[0], "*.docx")) {
  Console.WriteLine("== " + f);
  try {
    using var doc = WordprocessingDocument.Open(f, false);
    var v = new OpenXmlValidator(FileFormatVersions.Office2016);
    int n = 0;
    foreach (var e in v.Validate(doc)) { if (n++ < 25) Console.WriteLine($"{e.ErrorType} | {e.Description} | {e.Path?.XPath} | {e.Part?.Uri}"); }
    Console.WriteLine("so loi: " + n);
  } catch (Exception ex) { Console.WriteLine("KHONG MO DUOC: " + ex.Message); }
}
