"""Company profile form — all editable attributes."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, TextAreaField, SelectField,
                     IntegerField, SubmitField)
from wtforms.validators import DataRequired, Optional, Length, Email, URL, Regexp

INDIAN_STATES = [
    ('', '-- Select State --'),
    ('Andhra Pradesh','Andhra Pradesh'),('Arunachal Pradesh','Arunachal Pradesh'),
    ('Assam','Assam'),('Bihar','Bihar'),('Chhattisgarh','Chhattisgarh'),
    ('Goa','Goa'),('Gujarat','Gujarat'),('Haryana','Haryana'),
    ('Himachal Pradesh','Himachal Pradesh'),('Jharkhand','Jharkhand'),
    ('Karnataka','Karnataka'),('Kerala','Kerala'),('Madhya Pradesh','Madhya Pradesh'),
    ('Maharashtra','Maharashtra'),('Manipur','Manipur'),('Meghalaya','Meghalaya'),
    ('Mizoram','Mizoram'),('Nagaland','Nagaland'),('Odisha','Odisha'),
    ('Punjab','Punjab'),('Rajasthan','Rajasthan'),('Sikkim','Sikkim'),
    ('Tamil Nadu','Tamil Nadu'),('Telangana','Telangana'),('Tripura','Tripura'),
    ('Uttar Pradesh','Uttar Pradesh'),('Uttarakhand','Uttarakhand'),
    ('West Bengal','West Bengal'),
    ('Delhi','Delhi'),('Chandigarh','Chandigarh'),
    ('Jammu and Kashmir','Jammu and Kashmir'),('Ladakh','Ladakh'),
]

BUSINESS_TYPES = [
    ('', '-- Select Type --'),
    ('Manufacturer', 'Manufacturer'),
    ('Wholesaler', 'Wholesaler'),
    ('Retailer', 'Retailer'),
    ('Exporter', 'Exporter'),
    ('Manufacturer & Exporter', 'Manufacturer & Exporter'),
    ('Trader', 'Trader'),
]


class CompanyProfileForm(FlaskForm):
    # Basic
    name          = StringField('Company / Brand Name *', validators=[DataRequired(), Length(max=120)])
    tagline       = StringField('Tagline / Slogan', validators=[Optional(), Length(max=200)])
    description   = TextAreaField('About Your Business *',
                                  validators=[DataRequired(), Length(min=20, max=2000)])
    business_type = SelectField('Business Type', choices=BUSINESS_TYPES, validators=[Optional()])
    established_year = IntegerField('Established Year', validators=[Optional()])

    # Contact
    phone    = StringField('Phone / Mobile',
                           validators=[Optional(),
                           Regexp(r'^[6-9]\d{9}$', message='Enter valid 10-digit Indian mobile')])
    whatsapp = StringField('WhatsApp Number',
                           validators=[Optional(),
                           Regexp(r'^[6-9]\d{9}$', message='Enter valid 10-digit number')])
    email    = StringField('Business Email', validators=[Optional(), Email()])
    website  = StringField('Website URL', validators=[Optional(), Length(max=200)])

    # Address
    address_line1 = StringField('Address Line 1', validators=[Optional(), Length(max=256)])
    address_line2 = StringField('Landmark / Area', validators=[Optional(), Length(max=256)])
    city          = StringField('City', validators=[Optional(), Length(max=64)])
    state         = SelectField('State', choices=INDIAN_STATES, validators=[Optional()])
    postal_code   = StringField('PIN Code',
                                validators=[Optional(),
                                Regexp(r'^\d{6}$', message='Enter valid 6-digit PIN code')])

    # Business IDs
    gst_number = StringField('GST Number', validators=[Optional(), Length(max=20)])
    pan_number = StringField('PAN Number', validators=[Optional(), Length(max=20)])

    # Media
    logo   = FileField('Company Logo', validators=[Optional(),
                        FileAllowed(['jpg','jpeg','png','webp'], 'Images only')])
    banner = FileField('Banner Image', validators=[Optional(),
                        FileAllowed(['jpg','jpeg','png','webp'], 'Images only')])

    submit = SubmitField('Save Profile')
