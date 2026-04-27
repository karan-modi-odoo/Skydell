{
    "name": "Karan | Doctor Forum",
    "summary": "Karan | Doctor Forum",
    "description": """
    Forum enhancements for the doctor community:
    topic types with post templates, compliance confirmation on posting,
    comment notifications, weekly digest, and clinical insight highlight.
    """,
    "author": "Karan",
    "website": "",
    "category": "Website",
    "version": "18.0.0.1.3",
    "depends": ["website_forum", "adx_doctor_registration_portal", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/forum_post_mail_template.xml",
        "data/weekly_digest_email.xml",
        "data/procedure_type_data.xml",
        "views/forum_topic_type_views.xml",
        "views/forum_post_view.xml",
        "views/forum_frontend_templates.xml",
        "views/procedure_type_view.xml",
        "views/forum_post_design.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "adx_website_forum/static/src/js/forum_topic_type_handler.js",
            "adx_website_forum/static/src/js/forum_post_design.js",
            "adx_website_forum/static/src/css/forum_post_design.css",
            "adx_website_forum/static/src/css/procedure_type.css",
            "adx_website_forum/static/src/js/procedure_type.js",
        ],
    },
}
