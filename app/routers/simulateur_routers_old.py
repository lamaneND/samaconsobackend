from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from zeep import Client, Settings
from zeep.transports import Transport
from requests import Session
import logging
import urllib3
import ssl
import tempfile
from pathlib import Path
from datetime import datetime
import random
import json
import xmltodict
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from requests_pkcs12 import get

# Disable urllib3 warnings for unverified HTTPS requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Custom HTTPS Adapter for SSL context
class CustomHTTPSAdapter(HTTPAdapter):
    """Custom HTTPS adapter that handles SSL context with client certificates"""
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)
   
    def init_poolmanager(self, *args, **kwargs):
        if self.ssl_context:
            # Use the provided SSL context directly
            kwargs['ssl_context'] = self.ssl_context
            # Ensure urllib3 uses our context properly
            kwargs['cert_reqs'] = ssl.CERT_NONE
            kwargs['ca_certs'] = None
            kwargs['ca_cert_dir'] = None
        else:
            # Create default context with weak cipher support
            ctx = create_urllib3_context()
            try:
                ctx.set_ciphers('DEFAULT:@SECLEVEL=0')
            except:
                pass
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize APIRouter
simulateur_router = APIRouter(prefix="/simulateur_v1", tags=["simulateur"])

# SOAP Configuration
SOAP_WSDL_URL = "https://10.101.1.160:8443/xmlvend/xmlvend.wsdl"
SOAP_SERVICE_NAME = "TrialCreditVendRequest"

# Certificate configuration - certificate is in the same directory as this script
CERTIFICATE_DIR = Path(__file__).parent  # Same directory as the script
CERTIFICATE_PATH = CERTIFICATE_DIR / "414.pfx"
CERTIFICATE_PASSWORD = "9!!8..VaMeG8"

# Pydantic models for request/response
class TrialCreditVendRequest(BaseModel):
    meter_no: str
    amount: float

class TrialCreditVendResponse(BaseModel):
    success: bool
    response: str
    date_time: str
    unique_number: str
    meter_no: str
    amount: float
    http_status: int = None
    error: str = None

def generate_datetime():
    """Generate datetime in format YYYYMMDDHHMM"""
    return datetime.now().strftime("%Y%m%d%H%M")

def generate_unique_number():
    """Generate a unique number for the transaction"""
    return str(random.randint(10000, 99999))

def create_ssl_context_with_certificate():
    """
    Create SSL context that handles weak certificates and loads the client certificate
    """
    # Create SSL context with lower security settings for legacy systems
    # Use PROTOCOL_TLS_CLIENT for better compatibility
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except AttributeError:
        # Fallback for older Python versions
        context = ssl.create_default_context()
   
    # Allow weak cryptographic algorithms (MD5, SHA-1) - this fixes "certificate too weak" error
    try:
        context.set_ciphers('DEFAULT:@SECLEVEL=0')
    except Exception as e:
        logger.warning(f"Could not set ciphers: {e}")
        # Try alternative cipher setting
        try:
            context.set_ciphers('ALL:!aNULL:!eNULL:@SECLEVEL=0')
        except:
            pass
    if hasattr(ssl, "TLSVersion"):
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    if hasattr(ssl, "OP_NO_TLSv1_3"):
        context.options |= ssl.OP_NO_TLSv1_3
    # Disable hostname and certificate verification for self-signed certificates
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
   
    # Allow legacy protocols and ciphers
    context.options |= ssl.OP_LEGACY_SERVER_CONNECT
    
    # Additional options for legacy SSL/TLS support
    try:
        # Allow all TLS versions (including older ones)
        context.minimum_version = ssl.TLSVersion.MINIMUM_SUPPORTED
        context.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
    except AttributeError:
        # For older Python versions, set options directly
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        # Allow TLS 1.0, 1.1, 1.2, 1.3
        pass
   
    # Load client certificate if it exists
    if CERTIFICATE_PATH.exists():
        try:
            logger.info(f"Loading client certificate from: {CERTIFICATE_PATH}")
           
            # Read the .pfx file
            with open(CERTIFICATE_PATH, 'rb') as f:
                pfx_data = f.read()
           
            # Extract certificate and private key from .pfx
            password = CERTIFICATE_PASSWORD.encode() if CERTIFICATE_PASSWORD else None
           
            try:
                private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                    pfx_data, password
                )
                logger.info("Successfully loaded certificate from .pfx file")
                if additional_certificates:
                    logger.info(f"Found {len(additional_certificates)} additional certificate(s) in .pfx file")
            except Exception as cert_error:
                logger.error(f"Failed to decrypt certificate with provided password: {cert_error}")
                raise
            
            # Create temporary PEM files for certificate, key, and intermediate certificates
            cert_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pem', mode='wb')
            key_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pem', mode='wb')
            
            try:
                # Write main certificate
                cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
                cert_temp.write(cert_pem)
                
                # Write intermediate certificates (if any) - these are crucial for the certificate chain
                if additional_certificates:
                    for intermediate_cert in additional_certificates:
                        if intermediate_cert:
                            intermediate_pem = intermediate_cert.public_bytes(serialization.Encoding.PEM)
                            cert_temp.write(intermediate_pem)
                            logger.info("Added intermediate certificate to chain")
                
                cert_temp.flush()
                
                # Write private key
                key_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                key_temp.write(key_pem)
                key_temp.flush()
                
                # Load certificate and key into SSL context
                context.load_cert_chain(certfile=cert_temp.name, keyfile=key_temp.name)
                
                # Log certificate details for debugging
                logger.info("Client certificate (with intermediate certificates) loaded into SSL context")
                logger.debug(f"Certificate file: {cert_temp.name}")
                logger.debug(f"Key file: {key_temp.name}")
                if additional_certificates:
                    logger.info(f"Total certificates in chain: {1 + len(additional_certificates)}")
                
                # Store temp file paths for cleanup later if needed
                context._temp_cert_file = cert_temp.name
                context._temp_key_file = key_temp.name
               
            except Exception as e:
                cert_temp.close()
                key_temp.close()
                raise Exception(f"Failed to create temporary certificate files: {e}")
               
        except Exception as e:
            logger.error(f"Error loading client certificate: {e}")
            logger.warning("Proceeding without client certificate authentication")
    else:
        logger.warning(f"Certificate file not found at: {CERTIFICATE_PATH}")
        logger.warning("Proceeding without client certificate authentication")
   
    return context

def create_soap_request(meter_no: str, amount: float, date_time: str = None, unique_number: str = None):
    """Create SOAP XML request with dynamic values"""
    if not date_time:
        date_time = generate_datetime()
    if not unique_number:
        unique_number = generate_unique_number()
   
    soap_template = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
   <soapenv:Body>
      <ns2:trialCreditVendReq xmlns:ns2="http://www.nrs.eskom.co.za/xmlvend/revenue/2.1/schema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns2:TrialCreditVendReq">
         <clientID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="EANDeviceID" ean="0000000000414"/>
         <terminalID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="GenericDeviceID" id="0000000000414"/>
         <msgID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" dateTime="{date_time}" uniqueNumber="{unique_number}"/>
          <authCred xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema">
                <opName>AG0588</opName>
                <password>Senelec@123</password>
         </authCred>
         <resource xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="Electricity"/>
         <idMethod xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="VendIDMethod">
            <meterIdentifier xsi:type="MeterNumber" msno="{meter_no}"/>
         </idMethod>
         <ns2:purchaseValue xsi:type="ns2:PurchaseValueCurrency">
            <ns2:amt value="{amount}" symbol="AZM"/>
         </ns2:purchaseValue>
      </ns2:trialCreditVendReq>
   </soapenv:Body>
</soapenv:Envelope>"""
   
    return soap_template.format(
        date_time=date_time,
        unique_number=unique_number,
        meter_no=meter_no,
        amount=int(amount)  # Convert to int for the XML
    )

def parse_soap_response(xml_content: str, request_date_time: str, unique_number: str, http_status: int) -> dict:
    """
    Parse SOAP XML response and return structured JSON
    
    Args:
        xml_content: Raw XML SOAP response
        request_date_time: Original request datetime
        unique_number: Original request unique number
        http_status: HTTP status code of the response
        
    Returns:
        Structured JSON dictionary with parsed data
    """
    try:
        # Parse XML to dictionary
        parsed_xml = xmltodict.parse(xml_content)
        
        # Navigate through SOAP structure
        body = parsed_xml["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["ns3:trialCreditVendResp"]
        
        # Build structured JSON result
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
        
        return json_result
        
    except Exception as e:
        logger.error(f"Error parsing SOAP response: {e}", exc_info=True)
        # Return raw response if parsing fails
        return {
            "success": False,
            "http_status": http_status,
            "error": f"Failed to parse XML response: {str(e)}",
            "raw_response": xml_content
        }

@simulateur_router.post("/trial-credit-vend-request")
async def trial_credit_vend_request(request: TrialCreditVendRequest):
    from requests_pkcs12 import post as pkcs12_post
    """
    Call the TrialCreditVendRequest SOAP service
   
    - **meter_no**: Meter number to process
    - **amount**: Amount for the transaction
    """
    try:
        # Generate dynamic values
        date_time = generate_datetime()
        unique_number = generate_unique_number()
       
        logger.info(f"Processing TrialCreditVendRequest for meter: {request.meter_no}, amount: {request.amount}")
       
        # Create SSL context with client certificate
        ssl_context = create_ssl_context_with_certificate()
       
        # Create SOAP request XML
        soap_xml = create_soap_request(
            meter_no=request.meter_no,
            amount=request.amount,
            date_time=date_time,
            unique_number=unique_number
        )
       
        # Initialize endpoint URL (will be discovered from WSDL or use default)
        endpoint_url = SOAP_WSDL_URL.replace('.wsdl', '')
       
        # Try using zeep to connect to WSDL and call the service
        # Create requests session with SSL context
        session = Session()
        session.verify = False  # Disable server certificate verification
        session.mount('https://', CustomHTTPSAdapter(ssl_context=ssl_context))
       
        # Create transport with session
        transport = Transport(session=session, timeout=30)
       
        # Create zeep client with WSDL
        settings = Settings(strict=False, xml_huge_tree=True)
       
        try:
            logger.info(f"Connecting to WSDL: {SOAP_WSDL_URL}")
            client = Client(SOAP_WSDL_URL, transport=transport, settings=settings)
           
            # Try to find and call the TrialCreditVendRequest service
            # First, let's see what services are available
            logger.info("Available services in WSDL:")
            for service_name in client.wsdl.services:
                logger.info(f"  - Service: {service_name}")
                for port_name in client.wsdl.services[service_name].ports:
                    logger.info(f"    - Port: {port_name}")
           
            # Try to find the TrialCreditVendRequest service method
            # Since we have a specific XML template, we'll use direct SOAP request
            # but zeep helps us discover the service endpoint
            logger.info("WSDL loaded successfully. Discovering service endpoint...")
           
            # Get the service endpoint URL from the WSDL
            service = None
            for service_name in client.wsdl.services:
                service = client.wsdl.services[service_name]
                for port_name in service.ports:
                    port = service.ports[port_name]
                    # Try to get the endpoint URL from the port
                    try:
                        endpoint_url = port.binding._transport._address
                        logger.info(f"Found endpoint from WSDL: {endpoint_url}")
                        break
                    except:
                        pass
                if endpoint_url:
                    break
           
            # Since we have a specific XML template, use direct SOAP request
            # But zeep has validated the WSDL connection with our certificate
            # endpoint_url is already set from WSDL discovery or default
            raise Exception("Using direct SOAP request with validated WSDL connection")
               
        except Exception as zeep_error:
            # Check if this is our intentional exception for direct SOAP request
            if "Using direct SOAP request" in str(zeep_error):
                logger.info("Using direct SOAP request method (WSDL connection validated)...")
            else:
                logger.warning(f"Could not use zeep client method: {zeep_error}")
                logger.info("Falling back to direct SOAP request method...")
           
            # Send direct SOAP request using the session we created
            # Set SOAP headers
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'TrialCreditVendRequest',
                'Accept': 'text/xml'
            }
           
            logger.info(f"Sending SOAP request to: {endpoint_url}")
            logger.debug(f"SOAP Request XML:\n{soap_xml}")
           
            # Send SOAP request
            # response = session.post(
            #     endpoint_url,
            #     data=soap_xml,
            #     headers=headers,
            #     timeout=30
            # )
            from requests_pkcs12 import post as pkcs12_post
            response = pkcs12_post(
            endpoint_url,
            data=soap_xml,
            headers=headers,
            pkcs12_filename=str(CERTIFICATE_PATH),
            pkcs12_password=CERTIFICATE_PASSWORD,
            verify=False,
            timeout=30
             )
 
           
            logger.info(f"Received response with status code: {response.status_code}")
           
            # Parse the SOAP XML response into structured JSON
            parsed_response = parse_soap_response(
                xml_content=response.text,
                request_date_time=date_time,
                unique_number=unique_number,
                http_status=response.status_code
            )
            
            return parsed_response
           
    except Exception as e:
        logger.error(f"Error in TrialCreditVendRequest: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
                "certificate_path": str(CERTIFICATE_PATH),
                "certificate_exists": CERTIFICATE_PATH.exists()
            }
        )

@simulateur_router.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "TrialCreditVendRequest SOAP Client API",
        "endpoints": {
            "main": "/trial-credit-vend-request",
            "docs": "/docs"
        },
        "certificate_path": str(CERTIFICATE_PATH),
        "certificate_exists": CERTIFICATE_PATH.exists()
    }

@simulateur_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "certificate_configured": CERTIFICATE_PATH.exists(),
        "certificate_path": str(CERTIFICATE_PATH)
    }