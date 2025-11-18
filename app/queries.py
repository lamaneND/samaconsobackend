top10TransactionsQuery = """SELECT DISTINCT TOP 10 NUMERO_COMMANDE,
NUMERO_COMPTEUR,
POLICE,
NOM_AGENCE_ENCAISSEMENT
,TARIF_USAGE
,DATE_TRANSACTION
,MONTANT_HT
,MONTANT_TVA
,MONTANT_TCO
,MONTANT_TTC
,ENERGIE_VENDUE
, SOLDE_DETTE
,DETTES
,NOM_OPERATEUR
,TOKEN
,MONTANT_RECU
,ARRONDI,
ENERGIE1,
PRIX1,
MONTANT1,
ENERGIE2,
PRIX2,
MONTANT2,
ENERGIE3,
PRIX3,
MONTANT3
FROM HEXING_SENELECBILL_ALHDL2
WHERE NUMERO_COMPTEUR = ? AND POLICE = ?
ORDER BY DATE_TRANSACTION DESC
"""

getTransactionsByMonthMeterPoc = """
select 
	NUMERO_COMPTEUR,
	month(DATE_TRANSACTION) Mois,
	year(date_transaction) Annee,POLICE,
	sum(energie_vendue) [Total énergie],
	sum(coalesce(Montant_recu,montant_ttc)) [Total TTC]
from  HEXING_SENELECBILL_ALHDL2
where  year(DATE_TRANSACTION) = year(getdate()) and NUMERO_COMPTEUR = ?  and POLICE = ?
group by NUMERO_COMPTEUR,
	month(DATE_TRANSACTION),
	year(date_transaction),POLICE
order by cast(month(DATE_TRANSACTION) as int)"""

getBillsByMonth ="""
select 
	numcc,
	month(datfact) Mois,
	year(DATFACT) Annee,
	sum(BT_CONSTOT) [Total énergie],
	sum(BT_MONT_TTC) [Total TTC]
from  historique
where numCC = ? and year(DATFACT) = year(getdate())
group by numCC,
	month(DATFACT),
	year(DATFACT)
order by cast(month(DATFACT) as int)"""

getCustomerByPhoneQuery = "SELECT * from HEXING_INFOS_ADMINISTRATIVES where TELEPHONE=?"

getCustomerByMeterQuery="SELECT * from HEXING_INFOS_ADMINISTRATIVES where MT_COMM_ADDR=?"


top10TransactionsByPhoneNumberQuery = """SELECT DISTINCT TOP 10 NUMERO_COMMANDE,
NUMERO_COMPTEUR,
POLICE,
NOM_AGENCE_ENCAISSEMENT
,TARIF_USAGE
,DATE_TRANSACTION
,MONTANT_HT
,MONTANT_TVA
,MONTANT_TCO
,MONTANT_TTC
,ENERGIE_VENDUE
, SOLDE_DETTE
,DETTES
,NOM_OPERATEUR
,TOKEN
,MONTANT_RECU
,ARRONDI,
ENERGIE1,
PRIX1,
MONTANT1,
ENERGIE2,
PRIX2,
MONTANT2,
ENERGIE3,
PRIX3,
MONTANT3
FROM HEXING_SENELECBILL_ALHDL2
WHERE NUMERO_COMPTEUR IN(
SELECT MT_COMM_ADDR from HEXING_INFOS_ADMINISTRATIVES where TELEPHONE=?
)
ORDER BY DATE_TRANSACTION DESC
"""

transactionsBetweenDatesQuery = """SELECT DISTINCT  NUMERO_COMMANDE,
NUMERO_COMPTEUR,
POLICE,
NOM_AGENCE_ENCAISSEMENT
,TARIF_USAGE
,DATE_TRANSACTION
,MONTANT_HT
,MONTANT_TVA
,MONTANT_TCO
,MONTANT_TTC
,ENERGIE_VENDUE
, SOLDE_DETTE
,DETTES
,NOM_OPERATEUR
,TOKEN
,MONTANT_RECU
,ARRONDI,
ENERGIE1,
PRIX1,
MONTANT1,
ENERGIE2,
PRIX2,
MONTANT2,
ENERGIE3,
PRIX3,
MONTANT3
FROM HEXING_SENELECBILL_ALHDL2
WHERE NUMERO_COMPTEUR = ? AND POLICE=? AND (DATE_TRANSACTION BETWEEN ? AND ?)
ORDER BY DATE_TRANSACTION DESC
"""

top6FacturesQuery = """ SELECT DISTINCT TOP 6
Historique.IDHistorique AS IDHistorique,	
Historique.numFact AS numFact,	
Historique.numCC AS numCC,	
Historique.numPartenaire AS numPartenaire,	
Historique.dateEnvoi AS dateEnvoi,	
Historique.ADD_LIV AS ADD_LIV,	
Historique.ADD_PRES AS ADD_PRES,		
Historique.AI_TH1 AS AI_TH1,	
Historique.AGENCE AS AGENCE,			
Historique.BORDEREAU AS BORDEREAU,		
Historique.BT_MONT_HT AS BT_MONT_HT,	
Historique.BT_MONT_TTC AS BT_MONT_TTC,	
Historique.BT_MONT_TCO AS BT_MONT_TCO,	
Historique.BT_TOTALFACTUR AS BT_TOTALFACTUR,		
Historique.BT_CONSTOT as BT_CONSTOT,
Historique.MONT_TCO AS MONT_TCO,	
Historique.MONT_TTC AS MONT_TTC,	
Historique.MONT_TVA AS MONT_TVA,	
Historique.myTypeFact AS myTypeFact,	
Historique.NBJRS_ AS NBJRS_,		
Historique.NOCPTEUR AS NOCPTEUR,	
Historique.NOMPRES AS NOMPRES,	
Historique.PMAX AS PMAX,	
Historique.TARIF AS TARIF,		
Historique.TOTALFACT AS TOTALFACT,	
Historique.TYPEFACT AS TYPEFACT,		
Historique.moisFacturation AS moisFacturation,	
Historique.anneeFacturation AS anneeFacturation,	
Historique.typeClientele AS typeClientele,
Historique.DATFACT
FROM 
	Historique
WHERE 
	Historique.numCC = ? 
ORDER BY 
	DATFACT DESC
"""


FacturesbyPeriodQuery = """ SELECT DISTINCT
Historique.IDHistorique AS IDHistorique,	
Historique.numFact AS numFact,	
Historique.numCC AS numCC,	
Historique.numPartenaire AS numPartenaire,	
Historique.dateEnvoi AS dateEnvoi,	
Historique.ADD_LIV AS ADD_LIV,	
Historique.ADD_PRES AS ADD_PRES,		
Historique.AI_TH1 AS AI_TH1,	
Historique.AGENCE AS AGENCE,
Historique.BT_CONSTOT AS BT_CONSTOT,			
Historique.BORDEREAU AS BORDEREAU,		
Historique.BT_MONT_HT AS BT_MONT_HT,	
Historique.BT_MONT_TTC AS BT_MONT_TTC,	
Historique.BT_MONT_TCO AS BT_MONT_TCO,	
Historique.BT_TOTALFACTUR AS BT_TOTALFACTUR,		
Historique.MONT_TCO AS MONT_TCO,	
Historique.MONT_TTC AS MONT_TTC,	
Historique.MONT_TVA AS MONT_TVA,	
Historique.myTypeFact AS myTypeFact,	
Historique.NBJRS_ AS NBJRS_,		
Historique.NOCPTEUR AS NOCPTEUR,	
Historique.NOMPRES AS NOMPRES,	
Historique.PMAX AS PMAX,	
Historique.TARIF AS TARIF,		
Historique.TOTALFACT AS TOTALFACT,	
Historique.TYPEFACT AS TYPEFACT,		
Historique.moisFacturation AS moisFacturation,	
Historique.anneeFacturation AS anneeFacturation,	
Historique.typeClientele AS typeClientele,
Historique.DATFACT,
Historique.DATEECH [DATE_ECHEANCE],
Historique.BT_CONSOM1 [CONSO_TRANCHE1],
Historique.BT_CONSOM2 [CONSO_TRANCHE2],
Historique.BT_CONSOM3 [CONSO_TRANCHE3]
FROM 
	Historique
WHERE 
	Historique.numCC = ?  and (Historique.DATFACT between  ? and ? )
ORDER BY 
	DATFACT DESC
"""

getCustomerPostpaidByPhoneQuery ="""select distinct top 5 SUBSTRING(FKKVKP.VKONT, PATINDEX('%[^0]%', FKKVKP.VKONT+'.'), LEN(FKKVKP.VKONT)) [COMPTE CONTRAT]
,SUBSTRING(BUT000.PARTNER, PATINDEX('%[^0]%', BUT000.PARTNER+'.'), LEN(BUT000.PARTNER)) [N PARTENAIRE]
,  (BUT000.NAME_LAST + ' ' + BUT000.NAME_FIRST)  as [CLIENT] 
,adr2.Telnr_call TELEPHONE, ADR6.SMTP_ADDR EMAIL
from BUT000 LEFT JOIN ADR2 on BUT000.ADDRCOMM = ADR2.ADDRNUMBER
LEFT JOIN ADR6 on  ADR6.ADDRNUMBER = BUT000.ADDRCOMM,FKKVKP
where  BUT000.PARTNER = FKKVKP.GPART and vkont not like '023%' 
       and TELNR_CALL =?
 """

getDetailsCompteurPostpaiement = """select top 1 nompres,add_liv,numcc,numpartenaire,tarif
from historique
where numcc = ?"""
 
 

sixLastBills = """select top 6 BT_MONT_TTC MONTANT,
	numCC,numFact,DATFACT [DATFACT],DATEECH [DATE_ECHEANCE],
	BT_CONSOM1 [CONSO_TRANCHE1],
	BT_CONSOM2 [CONSO_TRANCHE2],
	BT_CONSOM3 [CONSO_TRANCHE3],
	BT_CONSTOT [CONSOMMATION TOTALE],
	NBJRS_ 
 
from historique
where numcc = ?
order by DATFACT desc"""
 

tenLastWoyofalTransactions = """select top 10 coalesce(Montant_recu,MONTANT_TTC) [MONTANT TTC],
	ENERGIE_VENDUE,
	DATE_TRANSACTION,
	NUMERO_COMPTEUR,
	TOKEN,
	DETTES,
	SOLDE_DETTE,
	POLICE,
    ENERGIE1,
	PRIX1,
	MONTANT1,
	ENERGIE2,
	PRIX2,
	MONTANT2,
	ENERGIE3,
	PRIX3,
	MONTANT3
from HEXING_SENELECBILL_ALHDL2 b, HEXING_INFOS_ADMINISTRATIVES_NEW a
where a.[N° COMPTEUR] = ? and a.[N° COMPTEUR] = b.NUMERO_COMPTEUR and a.POC = b.POLICE
order by b.DATE_TRANSACTION desc"""


verifierSiCompteurWoyofalExiste = """select poc, tel,[N° CLIENT] as id_client,ADRESSE as adresse,usage,CLIENT as nomClient,agence from HEXING_INFOS_ADMINISTRATIVES_NEW where [N° COMPTEUR] = ?"""

verifierSiCompteurClassiqueExiste1 = """" 
select distinct SUBSTRING(FKKVKP.VKONT, PATINDEX('%[^0]%', FKKVKP.VKONT+'.'), LEN(FKKVKP.VKONT)) [numCC]
,SUBSTRING(BUT000.PARTNER, PATINDEX('%[^0]%', BUT000.PARTNER+'.'), LEN(BUT000.PARTNER)) [idPartenaire]
,adr2.Telnr_call TELEPHONE as tel, h.add_liv adresse,H.Tarif,H.NomPres as nomClient
from BUT000 LEFT JOIN ADR2 on BUT000.ADDRCOMM = ADR2.ADDRNUMBER
LEFT JOIN ADR6 on  ADR6.ADDRNUMBER = BUT000.ADDRCOMM left join FKKVKP on  BUT000.PARTNER = FKKVKP.GPART left join [SRV-COMMERCIAL].[HISTH2MC].[dbo].[Historique] h on SUBSTRING(FKKVKP.VKONT, PATINDEX('%[^0]%', FKKVKP.VKONT+'.'), LEN(FKKVKP.VKONT)) = h.numcc
where SUBSTRING(FKKVKP.VKONT, PATINDEX('%[^0]%', FKKVKP.VKONT+'.'), LEN(FKKVKP.VKONT)) = ? """


verifierSiCompteurClassiqueExiste = """ select * from compteurs_postpaid where [COMPTE CONTRAT] = ? """

getSeuilsTarifQuery = """
SELECT 
  id,
  code_tarif,
  id_seuil,
  kwh_min,
  kwh_max,
  color_hex
FROM seuil_tarif
WHERE code_tarif like ?
ORDER BY id_seuil
"""

insertCompteur = """
INSERT INTO [dbo].[compteurs_app_mobile]
           ([numero]
           ,[type_compteur]
           )
     VALUES (?,?)
"""