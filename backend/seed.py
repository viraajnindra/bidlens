import json

from backend.engine import validate_evidence
from backend.models import ROOT, Document, Opportunity, Profile, Requirement, Session, init_db


def seed():
    init_db()
    fixture = json.loads((ROOT / "data/demo.json").read_text())
    documents = {d["id"]: d for d in fixture["documents"]}
    for req in fixture["requirements"]:
        validate_evidence(req["body"]["evidence"], documents)
    with Session.begin() as session:
        if not session.get(Opportunity, fixture["opportunity"]["id"]):
            opportunity = Opportunity(**fixture["opportunity"])
            session.add(opportunity)
            for doc in fixture["documents"]:
                session.add(
                    Document(
                        **doc,
                        opportunity_id=opportunity.id,
                        mode="reviewed_demo",
                        path=str(ROOT / "data/sources" / (doc["id"] + ".pdf")),
                    )
                )
            for req in fixture["requirements"]:
                session.add(Requirement(**req, opportunity_id=opportunity.id))
        if not session.get(Profile, "default"):
            session.add(Profile(**fixture["profile"]))


if __name__ == "__main__":
    seed()
    print("BidLens demo is ready.")
