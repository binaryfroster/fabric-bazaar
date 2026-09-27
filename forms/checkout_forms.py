"""Checkout form — Indian addresses + Razorpay payment."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp

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
    ('Andaman and Nicobar Islands','Andaman and Nicobar Islands'),
    ('Chandigarh','Chandigarh'),('Dadra and Nagar Haveli','Dadra and Nagar Haveli'),
    ('Daman and Diu','Daman and Diu'),('Delhi','Delhi'),('Lakshadweep','Lakshadweep'),
    ('Puducherry','Puducherry'),('Jammu and Kashmir','Jammu and Kashmir'),
    ('Ladakh','Ladakh'),
]

class CheckoutForm(FlaskForm):
    first_name    = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name     = StringField('Last Name',  validators=[DataRequired(), Length(max=64)])
    email         = StringField('Email',       validators=[DataRequired(), Email()])
    phone         = StringField('Mobile Number',
                                validators=[DataRequired(), Length(min=7, max=15)])
    address_line1 = StringField('Address Line 1', validators=[DataRequired(), Length(max=256)])
    address_line2 = StringField('Address Line 2 (Landmark / Flat no.)', validators=[Optional(), Length(max=256)])
    city          = StringField('City / District', validators=[DataRequired(), Length(max=64)])
    state         = SelectField('State', choices=INDIAN_STATES, validators=[DataRequired(message='Please select your state')])
    postal_code   = StringField('PIN Code',
                                validators=[DataRequired(),
                                Regexp(r'^\d{6}$', message='Enter a valid 6-digit PIN code')])
    country       = StringField('Country', default='India', render_kw={'readonly': True})
    notes         = TextAreaField('Order Notes (optional)', validators=[Optional(), Length(max=500)])
    submit        = SubmitField('Proceed to Payment')
