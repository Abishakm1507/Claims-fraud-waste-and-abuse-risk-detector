from backend.data import warehouse as wh

print("\nHIGHEST RISK (data + score):")
for r in wh.query("""
    SELECT ps.npi, ps.last_or_org_name AS name, ps.specialty,
           ps.state, ps.total_payment, pr.risk_score, pr.risk_tier
    FROM provider_summary ps
    JOIN provider_risk pr ON ps.npi = pr.npi
    ORDER BY pr.risk_score DESC LIMIT 10
"""):
    print(f"  {r['npi']}  {str(r['name'])[:20]:<20} {str(r['specialty'])[:22]:<22} "
          f"{r['state']}  ${r['total_payment'] or 0:>13,.0f}  "
          f"{r['risk_score']:.1f} {r['risk_tier']}")

print("\nLOW RISK (for contrast):")
for r in wh.query("""
    SELECT ps.npi, ps.last_or_org_name AS name, ps.specialty,
           ps.state, ps.total_payment, pr.risk_score, pr.risk_tier
    FROM provider_summary ps
    JOIN provider_risk pr ON ps.npi = pr.npi
    WHERE LOWER(pr.risk_tier) IN ('low', 'moderate')
    ORDER BY ps.total_payment DESC LIMIT 5
"""):
    print(f"  {r['npi']}  {str(r['name'])[:20]:<20} {str(r['specialty'])[:22]:<22} "
          f"{r['state']}  ${r['total_payment'] or 0:>13,.0f}  "
          f"{r['risk_score']:.1f} {r['risk_tier']}")