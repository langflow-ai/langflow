import React, { useState } from 'react';
import * as RadioGroup from '@radix-ui/react-radio-group';

// Phương thức 1: Import cụ thể theo từng thành phần
// Phương thức này nên được sử dụng thay vì import dạng namespace (* as RadioGroup)
import { Root, Item } from '@radix-ui/react-radio-group';

// Ví dụ cách sử dụng khi import cụ thể
function RadioGroupExample1() {
  const [value, setValue] = useState('default');
  
  return (
    <Root 
      className="flex gap-2" 
      value={value} 
      onValueChange={setValue}
    >
      <div className="flex items-center">
        <Item id="r1" value="option1" className="sr-only" />
        <label htmlFor="r1">Option 1</label>
      </div>
      
      <div className="flex items-center">
        <Item id="r2" value="option2" className="sr-only" />
        <label htmlFor="r2">Option 2</label>
      </div>
    </Root>
  );
}

// Ví dụ cách sử dụng khi import namespace
function RadioGroupExample2() {
  const [value, setValue] = useState('default');
  
  return (
    <RadioGroup.Root 
      className="flex gap-2" 
      value={value} 
      onValueChange={setValue}
    >
      <div className="flex items-center">
        <RadioGroup.Item id="r1" value="option1" className="sr-only" />
        <label htmlFor="r1">Option 1</label>
      </div>
      
      <div className="flex items-center">
        <RadioGroup.Item id="r2" value="option2" className="sr-only" />
        <label htmlFor="r2">Option 2</label>
      </div>
    </RadioGroup.Root>
  );
}

// Một phương thức giải quyết vấn đề khác nếu RadioGroup.Item gây lỗi
// là sử dụng destructuring từ import
function RadioGroupExample3() {
  const [value, setValue] = useState('default');
  
  return (
    <RadioGroup.Root 
      className="flex gap-2" 
      value={value} 
      onValueChange={setValue}
    >
      {/* Sử dụng HTML radio thông thường được liên kết với RadioGroup.Root */}
      <div className="flex items-center">
        <input 
          type="radio" 
          id="r1" 
          name="radiogroup" 
          value="option1" 
          checked={value === 'option1'} 
          onChange={() => setValue('option1')} 
          className="sr-only" 
        />
        <label htmlFor="r1">Option 1</label>
      </div>
      
      <div className="flex items-center">
        <input 
          type="radio" 
          id="r2" 
          name="radiogroup" 
          value="option2" 
          checked={value === 'option2'} 
          onChange={() => setValue('option2')} 
          className="sr-only" 
        />
        <label htmlFor="r2">Option 2</label>
      </div>
    </RadioGroup.Root>
  );
}

export { RadioGroupExample1, RadioGroupExample2, RadioGroupExample3 };