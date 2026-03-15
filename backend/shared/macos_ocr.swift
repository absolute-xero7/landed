import Foundation
import ImageIO
import Vision

struct OCRPage: Codable {
    let path: String
    let text: String
}

func recognizeText(at path: String) -> OCRPage {
    let url = URL(fileURLWithPath: path)
    guard
        let source = CGImageSourceCreateWithURL(url as CFURL, nil),
        let cgImage = CGImageSourceCreateImageAtIndex(source, 0, nil)
    else {
        return OCRPage(path: path, text: "")
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US", "fr-FR"]

    let handler = VNImageRequestHandler(cgImage: cgImage, orientation: .up, options: [:])
    do {
        try handler.perform([request])
    } catch {
        return OCRPage(path: path, text: "")
    }

    let text = request.results?
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: "\n") ?? ""

    return OCRPage(path: path, text: text)
}

let imagePaths = Array(CommandLine.arguments.dropFirst())
let pages = imagePaths.map(recognizeText)

let encoder = JSONEncoder()
if let data = try? encoder.encode(pages), let json = String(data: data, encoding: .utf8) {
    print(json)
} else {
    print("[]")
}
