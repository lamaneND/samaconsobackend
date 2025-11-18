# app/routers/simulateur_router.py
# SOAP XMLVend mTLS avec PFX — Adapter TLS1.2 + SECLEVEL=0 + endpoint override fiable
# - PFX direct (pas de PEM persistants)
# - Force TLS 1.2, SECLEVEL=0, désactive TLS 1.3
# - Présente la chaîne complète du PFX (feuille + intermédiaires)
# - Si le WSDL fournit un host "placeholder"/non résoluble, on force un endpoint override

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging, random, tempfile, os, ssl, socket
from xml.etree import ElementTree as ET
import xmltodict
from urllib.parse import urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -----------------------------------------------------------------------------
# Config (chemins identiques à ton projet)
# -----------------------------------------------------------------------------
SOAP_WSDL_URL = "https://10.101.1.160:8443/xmlvend/xmlvend.wsdl"
SOAP_SERVICE_NAME = "TrialCreditVendRequest"

CERTIFICATE_DIR = Path(__file__).parent

CERTIFICATE_PATH = CERTIFICATE_DIR / "487.pfx"
CERTIFICATE_PASSWORD = "Snlc@221...Pwd"


# Optionnel: override explicite (FQDN/URL de SoapUI si différent)
XMLVEND_ENDPOINT = os.getenv("XMLVEND_ENDPOINT", "").strip()  # ex: https://xmlvend.mon-domaine.local:8443/xmlvend

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

simulateur_router = APIRouter(prefix="/simulateur", tags=["simulateur"])

# -----------------------------------------------------------------------------
# Adapter HTTPS : TLS1.2 + SECLEVEL=0 + PFX
# -----------------------------------------------------------------------------
class Pkcs12TLS12LegacyAdapter(HTTPAdapter):
    __slots__ = ("_ssl_context", "_certfile", "_keyfile", "_tmp_files")

    def __init__(self, pkcs12_filename: str, pkcs12_password: str, **kwargs):
        certfile, keyfile, tmp_files = self._pfx_to_temp_pems(pkcs12_filename, pkcs12_password)
        ctx = self._build_ssl_context(certfile, keyfile)
        self._ssl_context = ctx
        self._certfile = certfile
        self._keyfile = keyfile
        self._tmp_files = tmp_files
        super().__init__(**kwargs)

    @staticmethod
    def _pfx_to_temp_pems(pkcs12_filename: str, pkcs12_password: str):
        with open(pkcs12_filename, "rb") as f:
            pfx = f.read()
        key, cert, add_certs = load_key_and_certificates(pfx, pkcs12_password.encode("utf-8"))
        if cert is None or key is None:
            raise RuntimeError("PFX invalide: certificat ou clé absents")

        tmp_files = []
        cert_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        cert_tmp.write(cert.public_bytes(Encoding.PEM))
        if add_certs:
            for c in add_certs:
                cert_tmp.write(c.public_bytes(Encoding.PEM))
        cert_tmp.flush()
        tmp_files.append(cert_tmp.name)

        key_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        key_tmp.write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
        key_tmp.flush()
        tmp_files.append(key_tmp.name)

        return cert_tmp.name, key_tmp.name, tmp_files

    @staticmethod
    def _build_ssl_context(certfile: str, keyfile: str) -> ssl.SSLContext:
        ctx = create_urllib3_context()
        if hasattr(ssl, "TLSVersion"):
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        if hasattr(ssl, "OP_NO_TLSv1_3"):
            ctx.options |= ssl.OP_NO_TLSv1_3
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        except ssl.SSLError:
            pass
        ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
        # DEV: pas de vérif serveur; PROD: fournissez un CA bundle (session.verify=...).
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        if "ssl_context" not in kwargs:
            kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(*args, **kwargs)

    def close(self):
        try:
            for p in getattr(self, "_tmp_files", []) or []:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
        finally:
            return super().close()

# -----------------------------------------------------------------------------
# Modèles
# -----------------------------------------------------------------------------
class TrialCreditVendRequest(BaseModel):
    meter_no: str
    amount: float

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def generate_datetime() -> str:
    return datetime.now().strftime("%Y%m%d%H%M")

def generate_unique_number() -> str:
    return str(random.randint(10000, 99999))

def create_soap_request(meter_no: str, amount: float, date_time: str, unique_number: str) -> str:
    return f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
   <soapenv:Body>
      <ns2:trialCreditVendReq xmlns:ns2="http://www.nrs.eskom.co.za/xmlvend/revenue/2.1/schema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns2:TrialCreditVendReq">
         <clientID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="EANDeviceID" ean="0000000000487"/>
         <terminalID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="GenericDeviceID" id="0000000000487"/>
         <msgID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" dateTime="{date_time}" uniqueNumber="{unique_number}"/>
          <authCred xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema">
                <opName>AG0158</opName>
                <password>Senelec@123</password>
         </authCred>
         <resource xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="Electricity"/>
         <idMethod xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="VendIDMethod">
            <meterIdentifier xsi:type="MeterNumber" msno="{meter_no}"/>
         </idMethod>
         <ns2:purchaseValue xsi:type="ns2:PurchaseValueCurrency">
            <ns2:amt value="{int(amount)}" symbol="AZM"/>
         </ns2:purchaseValue>
      </ns2:trialCreditVendReq>
   </soapenv:Body>
</soapenv:Envelope>"""
# f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
#    <soapenv:Body>
#       <ns2:trialCreditVendReq xmlns:ns2="http://www.nrs.eskom.co.za/xmlvend/revenue/2.1/schema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns2:TrialCreditVendReq">
#          <clientID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="EANDeviceID" ean="0000000000414"/>
#          <terminalID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="GenericDeviceID" id="0000000000414"/>
#          <msgID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" dateTime="{date_time}" uniqueNumber="{unique_number}"/>
#           <authCred xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema">
#                 <opName>AG0588</opName>
#                 <password>Senelec@123</password>
#          </authCred>
#          <resource xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="Electricity"/>
#          <idMethod xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="VendIDMethod">
#             <meterIdentifier xsi:type="MeterNumber" msno="{meter_no}"/>
#          </idMethod>
#          <ns2:purchaseValue xsi:type="ns2:PurchaseValueCurrency">
#             <ns2:amt value="{int(amount)}" symbol="AZM"/>
#          </ns2:purchaseValue>
#       </ns2:trialCreditVendReq>
#    </soapenv:Body>
# </soapenv:Envelope>"""

def _extract_endpoint_from_wsdl(wsdl_xml: str) -> Optional[str]:
    try:
        ns = {
            "wsdl": "http://schemas.xmlsoap.org/wsdl/",
            "soap": "http://schemas.xmlsoap.org/wsdl/soap/",
            "soap12": "http://schemas.xmlsoap.org/wsdl/soap12/",
        }
        root = ET.fromstring(wsdl_xml)
        for addr in root.findall(".//wsdl:service/wsdl:port/soap:address", ns):
            loc = addr.get("location")
            if loc:
                return loc
        for addr in root.findall(".//wsdl:service/wsdl:port/soap12:address", ns):
            loc = addr.get("location")
            if loc:
                return loc
    except Exception:
        pass
    return None

_PLACEHOLDER_TOKENS = ("manufacturer", "placeholder", "example", "changeme")

def _is_resolvable(hostname: str) -> bool:
    try:
        socket.getaddrinfo(hostname, None)
        return True
    except Exception:
        return False

def _compute_fallback_endpoint() -> str:
    """
    Fallback robuste:
    - si XMLVEND_ENDPOINT est défini (env), on l'utilise,
    - sinon: on prend schéma+netloc du WSDL et on force le path '/xmlvend'
    """
    if XMLVEND_ENDPOINT:
        return XMLVEND_ENDPOINT
    pu = urlparse(SOAP_WSDL_URL)
    base = pu._replace(path="/xmlvend", params="", query="", fragment="")
    return urlunparse(base)

def _sanitize_endpoint(wsdl_endpoint: Optional[str]) -> str:
    """
    Si le WSDL fournit un endpoint "clean" et résoluble → le garder.
    Sinon → fallback (env XMLVEND_ENDPOINT, ou base du WSDL /xmlvend).
    """
    # 1) priorité à XMLVEND_ENDPOINT si fourni
    if XMLVEND_ENDPOINT:
        return XMLVEND_ENDPOINT

    if not wsdl_endpoint:
        return _compute_fallback_endpoint()

    ep = urlparse(wsdl_endpoint)
    host = (ep.hostname or "").lower()

    # bloquer hosts manifestement placeholders ou non résolubles
    if any(tok in host for tok in _PLACEHOLDER_TOKENS) or not _is_resolvable(host):
        return _compute_fallback_endpoint()

    return wsdl_endpoint

def parse_soap_response(xml_content: str, request_date_time: str, unique_number: str, http_status: int) -> dict:
    try:
        parsed_xml = xmltodict.parse(xml_content)
        body = parsed_xml["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["ns3:trialCreditVendResp"]
        json_result = {
            "success": http_status == 200,
            "http_status": http_status,
            "error": None,
            "device_info": {
                "client_id": {
                    "ean": body.get("ns2:clientID", {}).get("@ean"),
                    "type": body.get("ns2:clientID", {}).get("@xsi:type")
                },
                "server_id": {
                    "ean": body.get("ns2:serverID", {}).get("@ean"),
                    "type": body.get("ns2:serverID", {}).get("@xsi:type")
                },
                "terminal_id": {
                    "id": body.get("ns2:terminalID", {}).get("@id"),
                    "type": body.get("ns2:terminalID", {}).get("@xsi:type")
                }
            },
            "transaction_info": {
                "response_date_time": body["ns2:respDateTime"],
                "request_date_time": request_date_time,
                "unique_number": unique_number,
                "receipt_no": body["ns3:creditVendReceipt"]["@receiptNo"],
                "display_header": body.get("ns2:dispHeader")
            },
            "utility": {
                "name": body.get("ns2:utility", {}).get("@name"),
                "address": body.get("ns2:utility", {}).get("@address")
            },
            "vendor": {
                "name": body.get("ns2:vendor", {}).get("@name"),
                "address": body.get("ns2:vendor", {}).get("@address")
            },
            "client": {
                "account_no": body["ns2:custVendDetail"]["@accNo"],
                "name": body["ns2:custVendDetail"]["@name"].strip(),
                "address": body["ns2:custVendDetail"]["@address"],
                "location_ref": body["ns2:custVendDetail"]["@locRef"],
                "days_since_last_purchase": int(body["ns2:custVendDetail"]["@daysLastPurchase"]),
                "available_credit": {
                    "currency": body["ns2:clientStatus"]["ns2:availCredit"]["@symbol"],
                    "value": float(body["ns2:clientStatus"]["ns2:availCredit"]["@value"])
                }
            }
        }
        
        # Extract transaction list
        tx_list = body["ns3:creditVendReceipt"]["ns3:transactions"]["ns3:tx"]
        if isinstance(tx_list, dict):
            tx_list = [tx_list]  # Force list if single element
        
        # Find different transaction types
        credit_tx = next((tx for tx in tx_list if "CreditVendTx" in tx["@xsi:type"]), None)
        debt_recovery_tx = next((tx for tx in tx_list if "DebtRecoveryTx" in tx["@xsi:type"]), None)
        service_charges = [tx for tx in tx_list if "ServiceChrgTx" in tx["@xsi:type"]]
        
        # Extract meter and purchase details
        if credit_tx:
            meter_detail = credit_tx["ns3:creditTokenIssue"]["ns2:meterDetail"]
            json_result["meter"] = {
                "number": meter_detail["@msno"],
                "sgc": meter_detail["@sgc"],
                "krn": meter_detail["@krn"],
                "ti": meter_detail["@ti"],
                "meter_type": {
                    "at": meter_detail.get("ns2:meterType", {}).get("@at"),
                    "tt": meter_detail.get("ns2:meterType", {}).get("@tt")
                },
                "max_vend_amount": float(meter_detail["ns2:maxVendAmt"]),
                "min_vend_amount": float(meter_detail["ns2:minVendAmt"]),
                "max_vend_energy": float(meter_detail["ns2:maxVendEng"]),
                "min_vend_energy": float(meter_detail["ns2:minVendEng"])
            }
            
            units = credit_tx["ns3:creditTokenIssue"]["ns2:units"]
            json_result["purchase"] = {
                "receipt_no": credit_tx.get("@receiptNo"),
                "amount": {
                    "value": float(credit_tx["ns3:amt"]["@value"]),
                    "currency": credit_tx["ns3:amt"]["@symbol"]
                },
                "units": {
                    "value": float(units["@value"]),
                    "unit": units["@siUnit"]
                },
                "tariff": {
                    "name": credit_tx.get("ns3:tariff", {}).get("ns2:name")
                },
                "resource_type": credit_tx["ns3:creditTokenIssue"].get("ns2:resource", {}).get("@xsi:type")
            }
            
            # Extract STS token (the real token!)
            token_issue = credit_tx["ns3:creditTokenIssue"]
            if "ns2:token" in token_issue:
                token = token_issue["ns2:token"]
                json_result["token"] = {
                    "type": token.get("@xsi:type"),
                    "sts_cipher": token.get("ns2:stsCipher", ""),
                    "description": token_issue.get("ns2:desc")
                }
            
            # Extract credit steps (tariff breakdown)
            if "ns3:creditStep" in credit_tx:
                json_result["credit_steps"] = []
                steps = credit_tx["ns3:creditStep"]["ns3:creditStepTx"]
                if isinstance(steps, dict):
                    steps = [steps]
                for step in steps:
                    # Handle empty/None values for stepE (can be empty for last step)
                    step_end_value = step.get("ns2:stepE")
                    step_end = None if not step_end_value or step_end_value == "" else int(step_end_value)
                    
                    step_begin_value = step.get("ns2:stepB", 0)
                    step_begin = 0 if not step_begin_value or step_begin_value == "" else int(step_begin_value)
                    
                    json_result["credit_steps"].append({
                        "step_begin": step_begin,
                        "step_end": step_end,  # Can be None for unlimited last step
                        "price_per_unit": float(step.get("ns2:price", 0)),
                        "amount": {
                            "value": float(step.get("ns2:amt", {}).get("@value", 0)),
                            "currency": step.get("ns2:amt", {}).get("@symbol")
                        },
                        "units": {
                            "value": float(step.get("ns2:units", {}).get("@value", 0)),
                            "unit": step.get("ns2:units", {}).get("@siUnit")
                        }
                    })
        
        # Extract debt recovery (includes BALANCE!)
        if debt_recovery_tx:
            json_result["debt_recovery"] = {
                "account_no": debt_recovery_tx.get("ns3:accNo"),
                "description": debt_recovery_tx.get("ns3:accDesc"),
                "amount": {
                    "value": float(debt_recovery_tx["ns3:amt"]["@value"]),
                    "currency": debt_recovery_tx["ns3:amt"]["@symbol"]
                },
                "balance": {
                    "value": float(debt_recovery_tx.get("ns3:balance", {}).get("@value", 0)),
                    "currency": debt_recovery_tx.get("ns3:balance", {}).get("@symbol")
                },
                "tariff": {
                    "name": debt_recovery_tx.get("ns3:tariff", {}).get("ns2:name")
                }
            }
        
        # Extract service charges
        json_result["service_charges"] = []
        for tx in service_charges:
            json_result["service_charges"].append({
                "type": "ServiceCharge",
                "account_no": tx.get("ns3:accNo"),
                "description": tx.get("ns3:accDesc"),
                "amount": {
                    "value": float(tx["ns3:amt"]["@value"]),
                    "currency": tx["ns3:amt"]["@symbol"]
                },
                "tariff": {
                    "name": tx.get("ns3:tariff", {}).get("ns2:name")
                }
            })
        
        # Extract transaction totals
        transactions = body["ns3:creditVendReceipt"]["ns3:transactions"]
        json_result["transaction_totals"] = {
            "less_round": {
                "value": float(transactions.get("ns3:lessRound", {}).get("@value", 0)),
                "currency": transactions.get("ns3:lessRound", {}).get("@symbol")
            },
            "tender_amount": {
                "value": float(transactions.get("ns3:tenderAmt", {}).get("@value", 0)),
                "currency": transactions.get("ns3:tenderAmt", {}).get("@symbol")
            },
            "change": {
                "value": float(transactions.get("ns3:change", {}).get("@value", 0)),
                "currency": transactions.get("ns3:change", {}).get("@symbol")
            }
        }
        return  json_result
        # {
        #     "success": http_status == 200,
        #     "http_status": http_status,
        #     "transaction_info": {
        #         "response_date_time": body["ns2:respDateTime"],
        #         "request_date_time": request_date_time,
        #         "unique_number": unique_number,
        #         "receipt_no": body["ns3:creditVendReceipt"]["@receiptNo"],
        #         "display_header": body.get("ns2:dispHeader")
        #     }
        # }
    except Exception as e:
        return {"success": False, "http_status": http_status, "error": f"parse error: {e}", "raw": xml_content}

# -----------------------------------------------------------------------------
# Endpoint principal
# -----------------------------------------------------------------------------
class _ReqModel(BaseModel):
    meter_no: str
    amount: float

@simulateur_router.post("/trial-credit-vend-request")
async def trial_credit_vend_request(request: _ReqModel):
    try:
        if not CERTIFICATE_PATH.exists():
            raise FileNotFoundError(f"Client certificate not found: {CERTIFICATE_PATH}")

        date_time = generate_datetime()
        unique_number = generate_unique_number()

        # Session Requests avec adapter PFX + TLS1.2 + SECLEVEL=0
        session = requests.Session()
        session.verify = False  # PROD: mettre un CA bundle ici
        session.mount("https://", Pkcs12TLS12LegacyAdapter(
            pkcs12_filename=str(CERTIFICATE_PATH),
            pkcs12_password=CERTIFICATE_PASSWORD
        ))

        # 1) GET WSDL (mTLS actif)
        wsdl_resp = session.get(SOAP_WSDL_URL, timeout=30)
        wsdl_resp.raise_for_status()

        # 2) Endpoint SOAP: WSDL → sanitize → fallback si non résoluble
        endpoint_raw = _extract_endpoint_from_wsdl(wsdl_resp.text)
        endpoint_url = _sanitize_endpoint(endpoint_raw)
        logger.info(f"SOAP endpoint selected: {endpoint_url}")

        # 3) Construire & POSTer la requête SOAP
        soap_xml = create_soap_request(
            meter_no=request.meter_no,
            amount=request.amount,
            date_time=date_time,
            unique_number=unique_number
        )
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": SOAP_SERVICE_NAME,
            "Accept": "text/xml",
        }

        resp = session.post(endpoint_url, data=soap_xml, headers=headers, timeout=60)
        parsed = parse_soap_response(resp.text, date_time, unique_number, resp.status_code)
        parsed["endpoint_used"] = endpoint_url
        parsed["openssl_version"] = getattr(ssl, "OPENSSL_VERSION", None)
        return parsed

    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e),
            "error_type": type(e).__name__,
            "certificate_path": str(CERTIFICATE_PATH),
            "certificate_exists": CERTIFICATE_PATH.exists(),
            "openssl_version": getattr(ssl, "OPENSSL_VERSION", None),
            "xmlvend_endpoint_env": XMLVEND_ENDPOINT or None
        })

# -----------------------------------------------------------------------------
# Utilitaire
# -----------------------------------------------------------------------------
@simulateur_router.get("/")
async def root():
    return {
        "message": "TrialCreditVendRequest SOAP Client API",
        "openssl_version": getattr(ssl, "OPENSSL_VERSION", None),
        "certificate_path": str(CERTIFICATE_PATH),
        "certificate_exists": CERTIFICATE_PATH.exists(),
        "wsdl": SOAP_WSDL_URL,
        "xmlvend_endpoint_env": XMLVEND_ENDPOINT or None
    }
