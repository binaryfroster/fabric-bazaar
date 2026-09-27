"""
Admin forms — Add / Edit product.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, TextAreaField, DecimalField, IntegerField,
                     SelectField, BooleanField, SubmitField)
from wtforms.validators import DataRequired, Optional, NumberRange, Length


SIZE_CHOICES = [
    ('', '-- Select size --'),
    ('Twin', 'Twin'),
    ('Twin XL', 'Twin XL'),
    ('Full', 'Full'),
    ('Queen', 'Queen'),
    ('King', 'King'),
    ('California King', 'California King'),
]

MATERIAL_CHOICES = [
    ('', '-- Select material --'),
    ('Egyptian Cotton', 'Egyptian Cotton'),
    ('Bamboo', 'Bamboo'),
    ('Microfiber', 'Microfiber'),
    ('Percale Cotton', 'Percale Cotton'),
    ('Sateen Cotton', 'Sateen Cotton'),
    ('Linen', 'Linen'),
    ('Tencel', 'Tencel'),
]

COLOR_CHOICES = [
    ('', '-- Select color --'),
    ('White', 'White'),
    ('Ivory', 'Ivory'),
    ('Beige', 'Beige'),
    ('Cream', 'Cream'),
    ('Grey', 'Grey'),
    ('Silver', 'Silver'),
    ('Navy', 'Navy'),
    ('Dusty Blue', 'Dusty Blue'),
    ('Sage Green', 'Sage Green'),
    ('Blush Pink', 'Blush Pink'),
    ('Charcoal', 'Charcoal'),
    ('Black', 'Black'),
]

ALLOWED = ['jpg', 'jpeg', 'png', 'webp']


class ProductForm(FlaskForm):
    name         = StringField('Product Name',    validators=[DataRequired(), Length(max=120)])
    description  = TextAreaField('Description',   validators=[DataRequired()])
    details      = TextAreaField('Fabric & Care Details', validators=[Optional()])
    price        = DecimalField('Price (ZAR)',     validators=[DataRequired(), NumberRange(min=0)],
                                places=2)
    sale_price   = DecimalField('Sale Price (ZAR, optional)',
                                validators=[Optional(), NumberRange(min=0)],
                                places=2)
    color        = SelectField('Color',            choices=COLOR_CHOICES,    validators=[Optional()])
    size         = SelectField('Size',             choices=SIZE_CHOICES,     validators=[Optional()])
    material     = SelectField('Material',         choices=MATERIAL_CHOICES, validators=[Optional()])
    thread_count = IntegerField('Thread Count',    validators=[Optional(), NumberRange(min=100, max=2000)])
    stock        = IntegerField('Stock Quantity',  validators=[DataRequired(), NumberRange(min=0)],
                                default=0)
    category_id  = SelectField('Category',         coerce=int, validators=[Optional()])

    is_featured   = BooleanField('Featured product')
    is_new        = BooleanField('Mark as New')
    is_bestseller = BooleanField('Mark as Bestseller')
    is_active     = BooleanField('Active (visible in shop)', default=True)

    image   = FileField('Primary Image',  validators=[Optional(), FileAllowed(ALLOWED)])
    image_2 = FileField('Image 2',        validators=[Optional(), FileAllowed(ALLOWED)])
    image_3 = FileField('Image 3',        validators=[Optional(), FileAllowed(ALLOWED)])
    image_4 = FileField('Image 4',        validators=[Optional(), FileAllowed(ALLOWED)])

    submit = SubmitField('Save Product')
