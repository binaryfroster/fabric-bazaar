"""Product form for company sellers."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, TextAreaField, DecimalField, IntegerField,
                     SelectField, BooleanField, SubmitField)
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from models.product import FABRIC_CATEGORIES, MATERIALS, SIZES, COLORS


class ProductForm(FlaskForm):
    name        = StringField('Product Name *', validators=[DataRequired(), Length(max=120)])
    description = TextAreaField('Description *', validators=[DataRequired(), Length(min=10)])
    details     = TextAreaField('Fabric / Care Details', validators=[Optional()])
    price       = DecimalField('Price (₹) *', validators=[DataRequired(), NumberRange(min=1)])
    sale_price  = DecimalField('Sale Price (₹)', validators=[Optional()], places=2)
    sku         = StringField('SKU / Product Code', validators=[Optional(), Length(max=64)])

    fabric_type = StringField('Product Category *', validators=[Optional(), Length(max=80)])
    material    = SelectField('Material / Fabric',
                              choices=[('', '-- Select --')] + [(x, x) for x in MATERIALS])
    color       = SelectField('Colour',
                              choices=[('', '-- Select --')] + [(x, x) for x in COLORS])
    size        = SelectField('Size',
                              choices=[('', '-- Select --')] + [(x, x) for x in SIZES])
    pattern     = StringField('Pattern', validators=[Optional(), Length(max=64)],
                              render_kw={'placeholder': 'e.g. Floral, Striped, Solid, Printed'})
    thread_count     = IntegerField('Thread Count', validators=[Optional()])
    care_instructions = StringField('Care Instructions', validators=[Optional(), Length(max=256)])

    stock           = IntegerField('Stock Quantity *', validators=[DataRequired(), NumberRange(min=0)])
    min_order_qty   = IntegerField('Min Order Qty', validators=[Optional(), NumberRange(min=1)], default=1)

    is_featured   = BooleanField('Feature this product on marketplace')
    is_new        = BooleanField('Mark as New Arrival')
    is_bestseller = BooleanField('Mark as Bestseller')

    image   = FileField('Main Image',   validators=[Optional(), FileAllowed(['jpg','jpeg','png','webp'])])
    image_2 = FileField('Image 2',      validators=[Optional(), FileAllowed(['jpg','jpeg','png','webp'])])
    image_3 = FileField('Image 3',      validators=[Optional(), FileAllowed(['jpg','jpeg','png','webp'])])
    image_4 = FileField('Image 4',      validators=[Optional(), FileAllowed(['jpg','jpeg','png','webp'])])

    submit = SubmitField('Save Product')

    def validate_sale_price(self, field):
        if field.data and self.price.data and field.data >= self.price.data:
            from wtforms import ValidationError
            raise ValidationError('Sale price must be less than the regular price.')
