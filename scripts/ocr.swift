// ocr.swift - OCR job-description screenshots with macOS Vision.
// Usage: swift ocr.swift /path/to/img1.png [/path/to/img2.png ...]
// Upscales 3x before recognition - proven on 295px-wide phone screenshots.
// Multiple screenshots of one post often overlap; dedupe when reading output.

import Foundation
import Vision
import AppKit

func ocrImage(at path: String) throws -> String {
    guard let image = NSImage(contentsOfFile: path),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        fatalError("Could not load image: \(path)")
    }

    // Upscale small images for better OCR accuracy
    let scale: CGFloat = 3.0
    let width = cgImage.width * Int(scale)
    let height = cgImage.height * Int(scale)
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                        space: colorSpace, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.interpolationQuality = .high
    ctx.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
    let scaled = ctx.makeImage()!

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: scaled, options: [:])
    try handler.perform([request])

    var lines: [String] = []
    for observation in request.results ?? [] {
        if let candidate = observation.topCandidates(1).first {
            lines.append(candidate.string)
        }
    }
    return lines.joined(separator: "\n")
}

let paths = Array(CommandLine.arguments.dropFirst())
if paths.isEmpty {
    print("Usage: swift ocr.swift /path/to/img1.png [/path/to/img2.png ...]")
    exit(2)
}
for path in paths {
    let text = try ocrImage(at: path)
    print("===== \(path) =====")
    print(text)
    print("")
}