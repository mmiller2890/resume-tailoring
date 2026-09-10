// pdfcheck.swift - verify a rendered resume PDF: page count, per-page breakdown,
// and whether probe strings extract from the text layer (the ATS "selectable text" check).
// Usage: swift pdfcheck.swift /path/to/resume.pdf "Test Owner" "keyword one" "keyword two" ...
// Exit codes: 0 = all probes found, 1 = some probe missing, 2 = cannot open PDF.

import PDFKit
import Foundation

let args = Array(CommandLine.arguments.dropFirst())
guard let pdfPath = args.first, let doc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else {
    print("Usage: swift pdfcheck.swift <pdf> [probe strings...]")
    exit(2)
}

let probes: [String] = args.dropFirst().map { String($0) }
print("Pages: \(doc.pageCount)")

let text = doc.string ?? ""
print("Extracted text length: \(text.count)")

var missing: [String] = []
for probe in probes {
    let found = text.contains(probe)
    print("Has '\(probe)': \(found)")
    if !found { missing.append(probe) }
}

print("--- PAGE BREAKDOWN ---")
for i in 0..<doc.pageCount {
    let pt = doc.page(at: i)?.string ?? ""
    let lines = pt.split(separator: "\n").map(String.init).filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
    let first = lines.first ?? "?"
    let last = lines.last ?? "?"
    print("Page \(i+1): \(lines.count) lines, starts: \(first.prefix(80)) ... ends: \(last.prefix(80))")
}

if missing.isEmpty {
    print("RESULT: PASS - all \(probes.count) probe strings extract from the text layer")
    exit(0)
} else {
    print("RESULT: FAIL - missing probes: \(missing.joined(separator: ", "))")
    exit(1)
}