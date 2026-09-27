"""
Contact page form.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length


SUBJECTS = [
    ('', '-- Select a subject --'),
    ('order',    'Order enquiry'),
    ('product',  'Product question'),
    ('shipping', 'Shipping & delivery'),
    ('returns',  'Returns & refunds'),
    ('other',    'Other'),
]


class ContactForm(FlaskForm):
    name    = StringField('Full Name',      validators=[DataRequired(), Length(max=128)])
    email   = StringField('Email Address',  validators=[DataRequired(), Email()])
    subject = SelectField('Subject',        choices=SUBJECTS, validators=[DataRequired()])
    message = TextAreaField('Message',      validators=[DataRequired(), Length(min=20, max=2000)])
    submit  = SubmitField('Send Message')
