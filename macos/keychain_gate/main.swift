// O Iris M-15 Keychain biometric gate helper (macOS). Apache-2.0.
// Commands: status | store (hex secret on stdin) | load [--reason R] | delete,
// each with --service S --account A. Output: one JSON object on stdout.
// Exit codes: 0 ok, 2 cancelled, 3 biometrics unavailable, 4 not found, 5 auth failed, 6 other error.
import Foundation
import LocalAuthentication
import Security

func emit(_ obj: [String: Any]) {
    if let d = try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys]) {
        FileHandle.standardOutput.write(d)
        FileHandle.standardOutput.write("\n".data(using: .utf8)!)
    }
}

func fail(_ code: Int32, _ msg: String) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(code)
}

func arg(_ name: String, _ def: String) -> String {
    let a = CommandLine.arguments
    if let i = a.firstIndex(of: name), i + 1 < a.count { return a[i + 1] }
    return def
}

func hexToData(_ s: String) -> Data? {
    let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
    guard t.count % 2 == 0 else { return nil }
    var out = Data(capacity: t.count / 2)
    var idx = t.startIndex
    while idx < t.endIndex {
        let next = t.index(idx, offsetBy: 2)
        guard let b = UInt8(t[idx..<next], radix: 16) else { return nil }
        out.append(b)
        idx = next
    }
    return out
}

func dataToHex(_ d: Data) -> String { d.map { String(format: "%02x", $0) }.joined() }

func biometry() -> (Bool, String) {
    let ctx = LAContext()
    var err: NSError?
    let ok = ctx.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &err)
    return (ok, ok ? "available" : (err?.localizedDescription ?? "unavailable"))
}

final class AuthBox: @unchecked Sendable {
    var ok = false
    var error: Error?
}

func authenticate(_ reason: String) -> LAContext {
    let (avail, detail) = biometry()
    if !avail { fail(3, detail) }
    let ctx = LAContext()
    ctx.localizedFallbackTitle = ""          // biometrics only: no password fallback
    let sem = DispatchSemaphore(value: 0)
    let box = AuthBox()
    ctx.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { ok, err in
        box.ok = ok
        box.error = err
        sem.signal()
    }
    sem.wait()
    if !box.ok {
        if let e = box.error as? LAError {
            switch e.code {
            case .userCancel, .appCancel, .systemCancel, .userFallback: fail(2, "cancelled")
            case .biometryNotAvailable, .biometryNotEnrolled, .biometryLockout: fail(3, "biometrics unavailable")
            default: break
            }
        }
        fail(5, "authentication failed")
    }
    return ctx
}

func baseQuery(_ service: String, _ account: String, dataProtection: Bool) -> [String: Any] {
    var q: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                            kSecAttrService as String: service,
                            kSecAttrAccount as String: account]
    if dataProtection { q[kSecUseDataProtectionKeychain as String] = true }
    return q
}

let cmd = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "status"
let service = arg("--service", "org.oiris.appgate")
let account = arg("--account", "master-slot")

switch cmd {
case "status":
    let (ok, detail) = biometry()
    emit(["biometry": ok, "detail": detail, "helper": "o-iris-keychain-gate", "version": 1])
case "store":
    let input = FileHandle.standardInput.readDataToEndOfFile()
    guard let hex = String(data: input, encoding: .utf8), let secret = hexToData(hex), secret.count == 32 else {
        fail(6, "expected 64 hex characters on stdin")
    }
    _ = authenticate("Enable Touch ID unlock for O Iris")
    for dp in [true, false] { SecItemDelete(baseQuery(service, account, dataProtection: dp) as CFDictionary) }
    var acErr: Unmanaged<CFError>?
    guard let ac = SecAccessControlCreateWithFlags(nil, kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
                                                   .biometryCurrentSet, &acErr) else { fail(6, "access control") }
    var q = baseQuery(service, account, dataProtection: true)
    q[kSecValueData as String] = secret
    q[kSecAttrAccessControl as String] = ac
    var st = SecItemAdd(q as CFDictionary, nil)
    var binding = "keychain-acl"
    if st == errSecMissingEntitlement {
        var legacy = baseQuery(service, account, dataProtection: false)
        legacy[kSecValueData as String] = secret
        st = SecItemAdd(legacy as CFDictionary, nil)
        binding = "la-check"
    }
    if st != errSecSuccess { fail(6, "SecItemAdd \(st)") }
    emit(["stored": true, "binding": binding])
case "load":
    let ctx = authenticate(arg("--reason", "Unlock O Iris"))
    for dp in [true, false] {
        var q = baseQuery(service, account, dataProtection: dp)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        q[kSecUseAuthenticationContext as String] = ctx
        var item: CFTypeRef?
        let st = SecItemCopyMatching(q as CFDictionary, &item)
        if st == errSecSuccess, let d = item as? Data {
            emit(["secret": dataToHex(d), "binding": dp ? "keychain-acl" : "la-check"])
            exit(0)
        }
        if st == errSecUserCanceled { fail(2, "cancelled") }
        if st == errSecAuthFailed { fail(5, "authentication failed") }
    }
    fail(4, "no gate secret stored")
case "delete":
    for dp in [true, false] { SecItemDelete(baseQuery(service, account, dataProtection: dp) as CFDictionary) }
    emit(["deleted": true])
default:
    fail(6, "unknown command \(cmd)")
}
