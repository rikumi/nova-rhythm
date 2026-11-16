"""Create an editable plan for semantic decomposition of static outfit artwork."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DESCRIPTIONS={
 '4003':'An anime action illustration with several fantasy adventurers, long flowing hair, weapons, lightning and a dark blue sky.',
 '4047':'An anime illustration of three girls around a circular wooden table with a map, envelopes and a lantern in a bright cozy room. An orange-haired girl in a red outfit is on the left, a dark-haired girl with goggles stands behind the table, and a blue-haired girl in a blue witch hat sits on the right. Letters and loose sheets of paper fly across the foreground. A sunny window, plants, chairs and a bed form the room.',
 '4008':'A bright colorful anime illustration of girls in a blue sky, with multicolored balloons, clouds, a flying vehicle and distant scenery.',
 '4007':'A dramatic dark blue anime illustration of a girl surrounded by flowing fabric, fantasy ornaments and yellow flowers.',
 '4046':'An anime illustration of a silver-haired girl in a softly lit wintry room, with warm furnishings, drinks and snowy light outside.',
 '4016':'An anime illustration of a silver-haired woman sitting on a grassy slope beneath pink flowering cherry trees, stretching her arms behind her head. She wears a white outfit with a brown corset and long dark blue ribbons. Long silver hair and ribbons flow across the image. The low angle view looks up at blue sky, cherry blossoms, pale tree trunks and pink petals. White daisies, yellow flowers, grass and a sword cross the foreground.',
 '4027':'An anime illustration of a red-haired girl in an ornate mechanical interior, with hanging structures, cables, windows and colorful fabric.',
 '4044':'An anime illustration in a warmly illuminated room with paper lanterns, a table, decorations and a person beside the furniture.',
 '4042':'An anime illustration of people in a warmly lit theatrical interior, with red curtains, a balcony railing and golden lantern light.',
 '4006':'An anime illustration of several fantasy girls performing music in a purple-lit magical room, with large musical instruments and dramatic effects.',
 '4043':'An anime illustration of several girls in a futuristic mechanical interior with a large circular machine, hanging structures and furniture.',
 '4004':'An anime illustration of girls resting together in a sunlit garden, with dark clothing, long pale hair, grass, plants and flowers.',
 '4005':'A luminous blue anime illustration of a girl in a flowing dress surrounded by water, light, flowers and fantasy scenery.',
 '4048':'A cheerful anime illustration of several small girls celebrating together in a warmly lit decorated room, surrounded by seasonal ornaments and gifts.',
 '4024':'An anime illustration of several girls resting in a green forest, with tree trunks, leafy plants and sunlight filtering through the canopy.',
 '4015':'An anime illustration of girls relaxing outdoors beneath leafy trees, with flowers, summer clothing and dappled sunshine.',
 '4040':'A dynamic anime illustration of a white-haired girl in a large mechanical outfit, with bright sunlight, equipment and motion effects.',
 '4017':'An anime illustration of a blonde girl at a summer festival at night, with colorful fireworks and festival decorations.',
 '4039':'An anime illustration of several girls and plush toys in a softly lit bedroom, with a very large pink rabbit plush, cushions and furniture.',
 '4038':'A swirling blue anime illustration with a girl floating among water, flowing hair, light effects and underwater scenery.',
 '4033':'A dramatic anime illustration of fantasy girls amid bones and skeletons, with dark clothing and warm golden light.',
 '4030':'An anime illustration of girls relaxing near a bright window in a furnished room, with chairs, a table, books and warm daylight.',
 '4022':'An anime illustration of girls seated together in a dark elegant room, with pale windows, furniture and purple accents.',
 '4013':'An anime illustration of girls sharing drinks in a warmly lit wood-paneled room, with a circular table, cups and dark red clothing.',
 '4012':'A dark blue anime illustration of several fantasy characters with animal motifs, long coats, weapons and an imposing indoor background.',
 '4011':'An anime illustration of girls beside a window on a rainy summer afternoon, with a white outfit, dark hair and a softly lit room.',
 '4009':'An anime illustration of several girls together in a bright vehicle interior, with seats, windows, school-style clothing and sunshine.',
 '4002':'A bright anime illustration of several girls in flowing fantasy outfits, surrounded by flowers, colorful light and a vivid blue sky.',
 '4001':'A vivid magenta anime album illustration of a girl in a large witch hat, with magical circular symbols, stars and luminous effects.',
 '3015':'A square anime album cover with two women standing back to back outdoors. The taller woman on the left has long dark blue hair and holds an ornate polearm. The woman on the right has long teal green hair and holds a small dark bird. Both wear light blue, white and pale yellow fantasy outfits. White birds fly across a blue sky with clouds and a faint rainbow. Green grass and white flowers frame the foreground. Large decorative yellow and white fictional lettering occupies the upper right, with small yellow lettering near the bottom.',
}
COMPLEX={'4003':5,'4008':5,'4047':5,'4006':5,'4048':6,'4024':5,'4039':5,'4033':5,'4022':5,'4009':5,'4002':5,'3004':5,'3002':5}

def main():
    catalog=json.loads((ROOT/'public/data/outfits.json').read_text(encoding='utf8'))
    items=[]
    for outfit in catalog['items']:
        if outfit['card']['layers']:continue
        code=outfit['code']
        generic=('A painted fantasy landscape album cover with distant scenery, sky, foreground objects and decorative lettering.' if code.startswith('1') else
                 'A stylized album cover with a central illustrated motif or mascot, decorative typography, graphic ornaments and a colorful background.' if code.startswith('2') else
                 'An anime album cover with the people, props, decorative typography and graphic elements visible in the source image.')
        caption=DESCRIPTIONS.get(code,generic)+" Preserve the original composition, crop, colors and lettering. The visible people are intact continuous figures, with their hair, faces, limbs, clothing and accessories belonging together. Continuous objects and props have unbroken silhouettes."
        items.append({'code':code,'outfit_id':outfit['id'],'name':outfit['name'],'source_url':outfit['staticImage'],'layers':COMPLEX.get(code,4),'caption':caption})
    plan={'schemaVersion':1,'model':'Qwen-Image-Layered','quantization':'unsloth Q4_K_M','seed':777,'steps':30,'cfg':4.0,'maximum_dimension':640,'minimum_layers':4,'maximum_layers':10,'items':items}
    path=ROOT/'references/experimental-layering-plan.json'
    path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Planned',len(items),'static outfits')

if __name__=='__main__':main()
