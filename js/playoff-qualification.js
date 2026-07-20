import{sortedStandings}from'./standings.js';

export function calculatePlayoffSeeds(league,standings,gameId){
  const conferences={};
  for(const conference of['East','West'])conferences[conference]=sortedStandings(league.filter(team=>team.conference===conference),standings,gameId).map((team,index)=>({teamId:team.id,seed:index+1,qualified:index<8,record:{wins:standings[team.id].wins,losses:standings[team.id].losses,pointDifferential:standings[team.id].pointDifferential,pointsFor:standings[team.id].pointsFor}}));
  return conferences;
}

export function validateQualification(seeding,league){const errors=[],ids=new Set(league.map(team=>team.id));for(const conference of['East','West']){const qualified=seeding[conference]?.filter(item=>item.qualified)||[],seeds=new Set(qualified.map(item=>item.seed));if(qualified.length!==8)errors.push(`${conference} has ${qualified.length} qualifiers.`);if(seeds.size!==8||![1,2,3,4,5,6,7,8].every(seed=>seeds.has(seed)))errors.push(`${conference} seeds are invalid.`);for(const item of qualified)if(!ids.has(item.teamId))errors.push(`Unknown qualified team ${item.teamId}.`)}return{valid:errors.length===0,errors}}

export function customQualification(customTeams,seeding){return customTeams.map(team=>{const entry=seeding[team.conference].find(item=>item.teamId===team.id);return{teamId:team.id,conference:team.conference,seed:entry.seed,qualified:entry.qualified,record:entry.record}})}
