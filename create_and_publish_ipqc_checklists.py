import os
import sys
import django
import openpyxl

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
from django.core.cache import cache
from org.models import Plant, Product, Department
from core.identity.models import Role
from forms_engine.models import (
    ChecklistTemplate,
    ChecklistVersion,
    ChecklistSection,
    ChecklistItem,
    ChecklistItemOption,
    ChecklistRule,
    TemplateRole,
)


def get_or_create_qa_dept():
    dept = Department.objects.filter(code="QA").first()
    if not dept:
        dept = Department.objects.filter(name__icontains="Quality").first()
    if not dept:
        raise ValueError("QA Department not found in database")
    return dept


def get_ipqc_role():
    role = Role.objects.filter(code="IPQC").first()
    if not role:
        raise ValueError("IPQC Role not found in database")
    return role


def create_result_section(version, section_order, prefix):
    section = ChecklistSection.objects.create(
        version=version,
        title="Results & Sign-off",
        order=section_order,
    )

    # Result dropdown
    item_res = ChecklistItem.objects.create(
        section=section,
        item_id=f"{prefix}_RES_01",
        label="Result:",
        item_type="DROPDOWN",
        required=True,
        order=1,
        severity_weight=0,
    )
    ChecklistItemOption.objects.create(item=item_res, label="PASS", value="PASS", order=0)
    ChecklistItemOption.objects.create(item=item_res, label="FAIL", value="FAIL", order=1)
    ChecklistItemOption.objects.create(item=item_res, label="Conditional Acceptance", value="CONDITIONAL ACCEPTANCE", order=2)

    # General Remark
    ChecklistItem.objects.create(
        section=section,
        item_id=f"{prefix}_RES_02",
        label="Overall Audit Remarks / Actions Required",
        item_type="TEXT",
        required=False,
        order=2,
        severity_weight=0,
    )
    return section


# =========================================================================
# 1. OLED AUDIT CHECKSHEET
# =========================================================================
def import_oled_checklist(all_plants, all_products, qa_dept, ipqc_role):
    print("\n--- Importing OLED Audit Checksheet ---")
    wb = openpyxl.load_workbook("OLED Audit checksheet.xlsx", data_only=True)
    ws = wb.active

    # Parse rows
    assembly_items = []
    trc_items = []
    defect_items = []

    current_type = "Assembly"
    for r in range(3, ws.max_row + 1):
        sn = ws.cell(r, 1).value
        type_val = ws.cell(r, 2).value
        check_item = ws.cell(r, 3).value

        if type_val:
            current_type = str(type_val).strip()

        if not check_item or str(check_item).strip().startswith("IPQC Sign") or str(check_item).strip().startswith("FORM NO"):
            continue

        item_text = str(check_item).strip()
        if "Assembly" in current_type:
            assembly_items.append(item_text)
        elif "TRC" in current_type:
            trc_items.append(item_text)
        elif "Defect" in current_type:
            defect_items.append(item_text)
        else:
            assembly_items.append(item_text)

    print(f"Parsed OLED: Assembly={len(assembly_items)}, TRC={len(trc_items)}, Defect={len(defect_items)}")

    template_code = "PADGET-QA-S-24-OLED-01A"
    template_name = "IPQC OLED Inspection Checksheet"
    description = (
        "Standard IPQC checksheet for auditing OLED screen assembly, jig impression and pressure, "
        "teflon tape protection, dummy runs, TRC repair controls, and defect rate monitoring."
    )

    with transaction.atomic():
        template, created = ChecklistTemplate.objects.get_or_create(
            code=template_code,
            defaults={
                "name": template_name,
                "description": description,
                "department": qa_dept,
                "approval_flow": "NONE",
                "is_active": True,
                "is_archived": False,
            },
        )
        if not created:
            template.name = template_name
            template.description = description
            template.department = qa_dept
            template.approval_flow = "NONE"
            template.is_active = True
            template.is_archived = False
            template.save()

        # Scope: all plants and models
        template.plants.set(all_plants)
        template.products.set(all_products)

        # Role assignment
        TemplateRole.objects.filter(template=template).delete()
        TemplateRole.objects.create(template=template, role=ipqc_role)

        # Deactivate old versions
        template.versions.all().delete()

        version = ChecklistVersion.objects.create(
            template=template,
            version_number=1,
            is_active=True,
            is_published=True,
        )

        sec_order = 1
        # Section 1: Assembly
        sec1 = ChecklistSection.objects.create(version=version, title="Assembly", order=sec_order)
        sec_order += 1
        for idx, text in enumerate(assembly_items, 1):
            rule_type = "PHOTO_REQUIRED" if ("wrap" in text.lower() or "diagram" in text.lower() or "impression" in text.lower()) else "REMARK_REQUIRED"
            item = ChecklistItem.objects.create(
                section=sec1,
                item_id=f"OLED_ASSY_{idx:02d}",
                label=text,
                item_type="BOOLEAN",
                required=True,
                order=idx,
                severity_weight=1,
            )
            ChecklistRule.objects.create(item=item, rule_type=rule_type, condition_value="NO")

        # Section 2: TRC
        sec2 = ChecklistSection.objects.create(version=version, title="TRC (Touch & Rework Center)", order=sec_order)
        sec_order += 1
        for idx, text in enumerate(trc_items, 1):
            rule_type = "PHOTO_REQUIRED" if "flow chart" in text.lower() else "REMARK_REQUIRED"
            item = ChecklistItem.objects.create(
                section=sec2,
                item_id=f"OLED_TRC_{idx:02d}",
                label=text,
                item_type="BOOLEAN",
                required=True,
                order=idx,
                severity_weight=1,
            )
            ChecklistRule.objects.create(item=item, rule_type=rule_type, condition_value="NO")

        # Section 3: Defect Rate Monitor
        sec3 = ChecklistSection.objects.create(version=version, title="Defect Rate Monitor", order=sec_order)
        sec_order += 1
        for idx, text in enumerate(defect_items, 1):
            item = ChecklistItem.objects.create(
                section=sec3,
                item_id=f"OLED_DEFECT_{idx:02d}",
                label=text,
                item_type="BOOLEAN",
                required=True,
                order=idx,
                severity_weight=1,
            )
            ChecklistRule.objects.create(item=item, rule_type="REMARK_REQUIRED", condition_value="NO")

        # Section 4: Results
        create_result_section(version, sec_order, "OLED")

    print(f"Created template: {template.code} - {template.name} (v1 published for {all_plants.count()} plants, {all_products.count()} products)")
    return template


# =========================================================================
# 2. NOTHING EMS BATTERY QUALITY CHECKLIST
# =========================================================================
def import_battery_checklist(all_plants, all_products, qa_dept, ipqc_role):
    print("\n--- Importing NOTHING EMS Battery Quality Control Checklist ---")
    wb = openpyxl.load_workbook("NOTHING EMS 工厂电池品质管控要求checklist.xlsx", read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    current_sec1 = None
    current_sec2 = None
    sections_dict = {}

    for r in rows[2:]:
        sn, sec1, sec2, content, risk = (r + (None, None, None, None, None))[:5]
        if not sn and not content:
            continue
        if str(sn).strip().startswith("1.划分") or "停产整顿" in str(sn):
            continue
        if sec1:
            current_sec1 = str(sec1).strip().replace("\n", " / ")
        if sec2:
            current_sec2 = str(sec2).strip().replace("\n", " / ")

        if not content:
            continue

        sec_name = current_sec1 or "General Quality Control"
        if sec_name not in sections_dict:
            sections_dict[sec_name] = []

        item_label = str(content).strip()
        if current_sec2 and not item_label.startswith(f"[{current_sec2}]"):
            item_label = f"[{current_sec2}]\n{item_label}"

        risk_str = str(risk).strip().upper() if risk else "B"
        if "A" in risk_str:
            weight = 3
        elif "B" in risk_str:
            weight = 2
        elif "C" in risk_str:
            weight = 1
        else:
            weight = 1

        sections_dict[sec_name].append({
            "sn": sn,
            "label": item_label,
            "weight": weight,
            "risk": risk_str,
        })

    print(f"Parsed Battery Checklist: {len(sections_dict)} sections, {sum(len(v) for v in sections_dict.values())} total items")

    template_code = "PADGET-QA-S-24-BATTERY-01A"
    template_name = "NOTHING EMS Battery Quality Control Checklist"
    description = (
        "Quality control audit checklist for battery handling across IQC incoming, warehouse storage, "
        "transportation, unpacking, assembly line, non-assembly, TRC dismantling, system traceability, and finished goods inventory."
    )

    with transaction.atomic():
        template, created = ChecklistTemplate.objects.get_or_create(
            code=template_code,
            defaults={
                "name": template_name,
                "description": description,
                "department": qa_dept,
                "approval_flow": "NONE",
                "is_active": True,
                "is_archived": False,
            },
        )
        if not created:
            template.name = template_name
            template.description = description
            template.department = qa_dept
            template.approval_flow = "NONE"
            template.is_active = True
            template.is_archived = False
            template.save()

        template.plants.set(all_plants)
        template.products.set(all_products)

        TemplateRole.objects.filter(template=template).delete()
        TemplateRole.objects.create(template=template, role=ipqc_role)

        template.versions.all().delete()

        version = ChecklistVersion.objects.create(
            template=template,
            version_number=1,
            is_active=True,
            is_published=True,
        )

        sec_order = 1
        for sec_title, items in sections_dict.items():
            section = ChecklistSection.objects.create(
                version=version,
                title=sec_title[:255],
                order=sec_order,
            )
            for idx, it in enumerate(items, 1):
                item = ChecklistItem.objects.create(
                    section=section,
                    item_id=f"BAT_{sec_order:02d}_{idx:02d}",
                    label=it["label"],
                    item_type="BOOLEAN",
                    required=True,
                    order=idx,
                    severity_weight=it["weight"],
                )
                ChecklistRule.objects.create(
                    item=item,
                    rule_type="REMARK_REQUIRED",
                    condition_value="NO",
                )
            sec_order += 1

        # Final Results section
        create_result_section(version, sec_order, "BAT")

    print(f"Created template: {template.code} - {template.name} (v1 published for {all_plants.count()} plants, {all_products.count()} products)")
    return template


# =========================================================================
# 3. IPQC BTB AUDIT CHECKSHEET
# =========================================================================
def import_btb_checklist(all_plants, all_products, qa_dept, ipqc_role):
    print("\n--- Importing IPQC BTB Audit Checksheet ---")
    wb = openpyxl.load_workbook("IPQC BTB Audit Checksheet.xlsx", data_only=True)
    ws = wb["Padget IN 2026 Checksheet"]

    sections_data = [
        {
            "title": "Checklist SOP Requirements (Inspection Frequency: SOP Publish Inspection)",
            "items": [
                "1. The BTB fastening position shall be marked as a critical position.",
                "2. When the main board and sub-board are put into operation, it is necessary to indicate that an ion air snake should be used to blow the sockets on the board to prevent poor buckling caused by foreign objects inside the sockets.",
                "3. For the BTB snap-fit fixture position, it is necessary to indicate that the fixture should be inspected before line start, confirming that the positioning pins of the fixture and the limit of the screw posts on the front shell are OK, and that there are no defects such as the fixture springs and limit blocks falling off.",
                "4. Precautions for BTB fastening: -- \n1) The SOP must be elaborated. Employees' fingernails must not extend beyond the fingertips. When fastening BTB connectors, fingertips should be used, and using fingernails is prohibited. \n2) For BTB mating, align the male connector on the FPC with the female connector on the main board, then gently slide the male connector left and right. When your finger feels the male connector naturally slide into the female connector on the board, press the male connector vertically to mate it with the female connector. \n3) After the BTB is properly mated, check that the BTB male socket reinforcement plate is flat and without tilt. If it is tilted, it is necessary to disassemble and realign it again.",
                "5. Except for the BTB on the TOP side, all BTBs must have a platform pressure compensation station.",
                "6. Products that fail to snap together on a single BTB connection need to be isolated and can be reused after repair and re-inspection.",
                "7. The BTB of the main FPC and the screen BTB must be fastened by designated personnel; no additional actions are permitted.",
                "8. After the screen is assembled into a three-in-one unit in the pre-processing section, it must be secured. Directly packing the screen with the FPC unsecured is prohibited, as packing with the FPC in a movable state risks scraping and deforming the BTB socket.",
            ],
        },
        {
            "title": "TRC Post-Inspection Items (Inspection Frequency: Line Inspection, Once a Day)",
            "items": [
                "1. Repairing or replacing BTB-related defects requires inspection with an electronic magnifying glass. Directly fastening and putting the device into production without magnifying glass inspection is not permitted.",
                "2. Defective main boards that need BTB disassembly should be marked as defective and returned to SMT for repair, and the failure categories should be properly recorded.",
                "3. The maintenance personnel are fixed, and it is necessary to verify whether they have the required work permits.",
                "4. Repairing defective BTB buckles, including issues such as appearance collapse and pin deformation, requires isolating and replacing the socket for repair; it must not be put into use.",
                "5. Make a trap prototype to test employees' re-inspection capabilities. For employees who cannot identify the trap machine, they need to be retrained and re-assessed.",
            ],
        },
        {
            "title": "Assembly Staff Inspection Items (Inspection Frequency: Line Inspection, Once a Day)",
            "items": [
                "1. IPQC randomly inspects 5 BTBs every 4 hours for misalignment, and detaches the male and female connectors, checking under a magnifying glass to ensure there are no defective collapses.",
                "2. Make a trap prototype to test employees' re-inspection capabilities. For employees who cannot detect the trap machine, they need to be retrained and re-assessed.",
                "3. BTB fastening station requires the use of BTB auxiliary fastening fixtures. The auxiliary fastening fixtures must be used as required, and it is prohibited to cancel them without permission.",
                "4. Verify whether the BTB position operator has a skill qualification certificate; it is prohibited for untrained employees to directly take up their posts.",
            ],
        },
        {
            "title": "BTB Pressure Supplement Clamp Inspection",
            "items": [
                "[Fixture Foreign Object Cleaning] Visually inspect the fixture indenter and base for foreign objects. Inspection frequency: Twice per shift. Standard: No foreign objects or leaks.",
                "[Head Pressing Position Accuracy] 1. Apply printing ink (red lead) to the indenter; 2. Take the well-fastened machine head and perform cold pressing; 3. Check the position of the ink on the BTB steel sheet; 4. Wipe off residual printing ink on indenter and BTB. Inspection Frequency: When fixture is used for the first time. Standard: On all BTBs, ink coverage must be >=90% with no missing areas on same side.",
                "[Pressure Audit] Confirm the actual pressure of the fixture indenter, conduct physical inspection, and verify the SOP standard. Standard: Fully 1.5N >= X >= 1N/pin.",
                "[Pressure-Sensitive Paper Effect Inspection] Is the pressure-sensitive effect of the fixture OK? Inspection Frequency: First Piece Inspection. Standard: Uniform pressure distribution.",
            ],
        },
        {
            "title": "BTB Fastening Fixture Inspection (First Piece Inspection / First Use)",
            "items": [
                "[Fixture's Limit Block to BTB] Visually inspect whether the limiting edge of the fixture is intact. Standard: 1. Place BTB into fixture slot, magnet must hold firmly. 2. All 3 side limiters must be intact without damage/deformation.",
                "[BTB Pressing Surface Inspection] Visually inspect whether contact surface between indenter and BTB steel sheet is flat and free of defects/foreign matter.",
                "[Head Pressing Position Accuracy] 1. Apply printing ink (red lead) to indenter; 2. Take well-fastened machine head and perform simulated fastening; 3. Check ink position on BTB steel sheet; 4. Wipe off residual ink. Standard: Ink centered on BTB steel sheet.",
                "[Pressure Audit] Confirm actual pressure of fixture indenter, conduct physical inspection and verify SOP standard. Standard: Fully 1.5N >= X >= 1N/pin.",
                "[Fixture Fastener Inspection] Inspect fixture screws; all screws must be tight and secure with no loosening.",
                "[Pressure-Sensitive Paper Effect Inspection] Is the pressure-sensitive effect of the fixture satisfactory? Standard: Uniform pressure distribution.",
            ],
        },
    ]

    template_code = "PADGET-QA-S-24-BTB-01A"
    template_name = "IPQC BTB Audit Checksheet"
    description = (
        "Audit checklist for BTB fastening SOP compliance, TRC repair inspection, assembly operator competency, "
        "BTB pressure supplement clamp validation, and BTB fastening fixture integrity."
    )

    with transaction.atomic():
        template, created = ChecklistTemplate.objects.get_or_create(
            code=template_code,
            defaults={
                "name": template_name,
                "description": description,
                "department": qa_dept,
                "approval_flow": "NONE",
                "is_active": True,
                "is_archived": False,
            },
        )
        if not created:
            template.name = template_name
            template.description = description
            template.department = qa_dept
            template.approval_flow = "NONE"
            template.is_active = True
            template.is_archived = False
            template.save()

        template.plants.set(all_plants)
        template.products.set(all_products)

        TemplateRole.objects.filter(template=template).delete()
        TemplateRole.objects.create(template=template, role=ipqc_role)

        template.versions.all().delete()

        version = ChecklistVersion.objects.create(
            template=template,
            version_number=1,
            is_active=True,
            is_published=True,
        )

        sec_order = 1
        for sec_data in sections_data:
            section = ChecklistSection.objects.create(
                version=version,
                title=sec_data["title"],
                order=sec_order,
            )
            for idx, text in enumerate(sec_data["items"], 1):
                rule_type = "PHOTO_REQUIRED" if ("paper" in text.lower() or "accuracy" in text.lower() or "limit block" in text.lower()) else "REMARK_REQUIRED"
                item = ChecklistItem.objects.create(
                    section=section,
                    item_id=f"BTB_{sec_order:02d}_{idx:02d}",
                    label=text,
                    item_type="BOOLEAN",
                    required=True,
                    order=idx,
                    severity_weight=1,
                )
                ChecklistRule.objects.create(
                    item=item,
                    rule_type=rule_type,
                    condition_value="NO",
                )
            sec_order += 1

        # Results section
        create_result_section(version, sec_order, "BTB")

    print(f"Created template: {template.code} - {template.name} (v1 published for {all_plants.count()} plants, {all_products.count()} products)")
    return template


def main():
    print("=== STARTING CHECKLIST IMPORT & PUBLISHING ===")
    all_plants = Plant.objects.all()
    all_products = Product.objects.all()
    qa_dept = get_or_create_qa_dept()
    ipqc_role = get_ipqc_role()

    print(f"Target Scope: {all_plants.count()} Plants ({[p.code for p in all_plants]})")
    print(f"Target Models: {all_products.count()} Products ({[pr.code for pr in all_products]})")
    print(f"Department: {qa_dept.name}")
    print(f"Role: {ipqc_role.name}")

    t1 = import_oled_checklist(all_plants, all_products, qa_dept, ipqc_role)
    t2 = import_battery_checklist(all_plants, all_products, qa_dept, ipqc_role)
    t3 = import_btb_checklist(all_plants, all_products, qa_dept, ipqc_role)

    # Clear application template cache
    cache.clear()
    print("\n[SUCCESS] Cleared application template cache.")
    print("=== CHECKLIST IMPORT & PUBLISH COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
