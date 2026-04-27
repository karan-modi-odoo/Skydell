{
    "name": "Karan | Doctor Registration",
    "summary": "Karan | Doctor Registration",
    "description": """
    Doctor registration portal with admin approval, country-based compliance,
    and compliance re-acceptance workflow.
    """,
    "author": "Karan",
    "website": "",
    "category": "Uncategorized",
    "version": "18.0.0.0.3",
    "depends": ["website", "mail", "contacts", "portal"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/website_menu.xml",
        "data/email_template.xml",
        "data/scheduled_action.xml",
        "wizard/registration_reject_wizard_views.xml",
        "views/doctor_registration_views.xml",
        "views/doctor_registration_template.xml",
        "views/country_compliance_views.xml",
        "views/doctor_specialty_views.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "adx_doctor_registration_portal/static/src/xml/compliance_popup.xml",
            "adx_doctor_registration_portal/static/src/js/compliance.js",
            "adx_doctor_registration_portal/static/src/js/compliance_popup.js",
            "adx_doctor_registration_portal/static/src/js/phone_picker.js",
        ],
    },
}
