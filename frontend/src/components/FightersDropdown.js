import React, { useState, useMemo } from 'react';
import { FixedSizeList as List } from 'react-window';
import './css/FightersDropdown.css';
import debounce from 'lodash.debounce';

const Row = ({ index, style, data }) => (
  <div style={style} className="fighter-item">{data[index]}</div>
);

const FightersDropdown = ({ fighters }) => {
  const [filter, setFilter] = useState('');

  // Efficiently filter and memoize the filtered list
  const filteredFighters = useMemo(() => 
    fighters.filter(fighter => fighter.toLowerCase().includes(filter.toLowerCase())),
    [filter, fighters]
  );

  // Debounce setFilter function to limit the number of updates
  const debouncedSetFilter = useMemo(() => debounce(setFilter, 300), []);

  const handleFilter = (event) => {
    debouncedSetFilter(event.target.value);
  };

  return (
    <div>
      <input type="text" onChange={handleFilter} placeholder="Search" />
      <List
        height={300} // Adjust based on your needs
        itemCount={filteredFighters.length}
        itemSize={35} // Adjust the size of each item
        width={300} // Adjust based on your needs
        itemData={filteredFighters} // Data passed to the list
      >
        {Row}
      </List>
    </div>
  );
};

export default FightersDropdown;
