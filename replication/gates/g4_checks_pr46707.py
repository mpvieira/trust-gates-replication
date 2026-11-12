"""G4 claim checks for PR #46707 (azure-confidentialledger, assert -> ValueError in receipt verification).
Run from sdk/confidentialledger/azure-confidentialledger, under `python` and `python -O`, at the merge commit and again
with _receipt_verification.py from the parent. Feeds four malformed receipts and one non-EC certificate through the
validation functions and reports accepted/ValueError for each."""
import sys
from azure.confidentialledger.receipt import _receipt_verification as rv
cases = {
 "missing signature": {"cert":"x","leafComponents":{"claimsDigest":"a","commitEvidence":"b","writeSetDigest":"c"},"proof":[]},
 "proof elem without left/right": {"cert":"x","leafComponents":{"claimsDigest":"a","commitEvidence":"b","writeSetDigest":"c"},"proof":[{"up":"z"}],"signature":"s"},
 "right not a str": {"cert":"x","leafComponents":{"claimsDigest":"a","commitEvidence":"b","writeSetDigest":"c"},"proof":[{"right":123}],"signature":"s"},
 "right-only elem, valid": {"cert":"x","leafComponents":{"claimsDigest":"a","commitEvidence":"b","writeSetDigest":"c"},"proof":[{"right":"abc"}],"signature":"s"},
}
for name, r in cases.items():
    try: rv._validate_receipt_content(r); print(f"  {name:32s} -> accepted", "(python -O)" if not __debug__ else "")
    except ValueError as e: print(f"  {name:32s} -> ValueError", "(python -O)" if not __debug__ else "")
    except AssertionError: print(f"  {name:32s} -> AssertionError")
# non-EC certificate
from cryptography import x509; from cryptography.hazmat.primitives import hashes, serialization; from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.x509.oid import NameOID; import datetime
k = rsa.generate_private_key(65537, 2048); n = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "t")])
c = x509.CertificateBuilder().subject_name(n).issuer_name(n).public_key(k.public_key()).serial_number(1).not_valid_before(datetime.datetime(2020,1,1)).not_valid_after(datetime.datetime(2030,1,1)).sign(k, hashes.SHA256())
pem = c.public_bytes(serialization.Encoding.PEM).decode()
try: rv._load_and_verify_pem_certificate(pem); print("  RSA cert                         -> accepted")
except ValueError as e: print("  RSA cert                         -> ValueError:", str(e)[:60].replace("\n"," "))
except Exception as e: print("  RSA cert                         ->", type(e).__name__, str(e)[:80])
